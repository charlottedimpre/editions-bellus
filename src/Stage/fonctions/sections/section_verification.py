import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from ...models import FicheSection, SectionTexte
from ...settings import BASE_DIR
from ..fiche_cadrage import recup_fiche_cadrage
from ..parser import read_text_file
from ..plan_detaille import recup_plan_detail
from ..structure_chapitre import recup_chapitres_sections

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT_DIR = Path(BASE_DIR).parents[0]
INPUT_DIR = Path(BASE_DIR) / "Stage/input/section/"

load_dotenv(ROOT_DIR / "param.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier param.env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
CLIENT = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _generate_text_with_retry(contents: str, context_label: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = CLIENT.models.generate_content(model=GEMINI_MODEL, contents=contents)
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError(f"Reponse vide de Gemini ({context_label}).")
            return text
        except ServerError as err:
            status_code = getattr(err, "status_code", None)
            is_503 = status_code == 503 or str(err).startswith("503")
            if not is_503:
                raise RuntimeError(f"Erreur serveur Gemini non 503 ({context_label}): {err}") from err
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Erreur 503 Gemini apres {MAX_RETRIES} tentatives ({context_label})."
                ) from err
            print(
                f"Gemini indisponible (503) [{context_label}] tentative {attempt}/{MAX_RETRIES}, "
                f"nouvelle tentative dans {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Aucune reponse exploitable de Gemini ({context_label}).")


# ---------------------------------------------------------------------------
# Helpers OUI/NON
# ---------------------------------------------------------------------------

def _parse_yes_no(text: str) -> bool | None:
    match = re.search(r"\b(OUI|NON)\b", text.strip().upper())
    if not match:
        return None
    return match.group(1) == "OUI"


def _extract_critique(text: str, is_valid: bool | None) -> str | None:
    if is_valid is True:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    match = re.search(r"\bNON\b\s*[:\-]?\s*(.+)", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if match:
        motif = match.group(1).strip()
        if motif:
            return motif
    return cleaned


def _is_non_actionable_critique(critique: str | None) -> bool:
    text = str(critique or "").strip().lower()
    if not text:
        return True
    markers = [
        "aucune correction", "aucun correctif", "pas de correction",
        "rien a corriger", "rien à corriger", "aucune anomalie",
        "aucun probleme", "aucun problème", "r.a.s", "ras",
    ]
    return any(marker in text for marker in markers)


def _normalize_non_actionable_non(result: dict[str, Any], gate_name: str) -> dict[str, Any]:
    normalized = dict(result)
    if normalized.get("decision") != "NON":
        return normalized
    if not _is_non_actionable_critique(normalized.get("critique")):
        return normalized
    normalized["decision"] = "OUI"
    normalized["critique"] = None
    normalized["normalisation"] = f"{gate_name}: NON non actionnable converti en OUI"
    return normalized


def _make_result(chapitre: int, section: int, response_text: str, extra: dict | None = None) -> dict[str, Any]:
    is_valid = _parse_yes_no(response_text)
    critique = _extract_critique(response_text, is_valid)
    result = {
        "chapitre": chapitre,
        "section": section,
        "decision": "OUI" if is_valid is True else "NON" if is_valid is False else "INDETERMINE",
        "critique": critique,
        "raw": response_text,
    }
    if extra:
        result.update(extra)
    return result


# ---------------------------------------------------------------------------
# Accès BDD locaux (évite l'import circulaire avec section.py)
# ---------------------------------------------------------------------------

def _get_section_texte(chapitre_num: int, section_num: int, livre_id: int) -> str:
    section = SectionTexte.objects.get(chapitre=chapitre_num, section=section_num, livre_id=livre_id)
    return json.dumps({
        "chapitre": section.chapitre,
        "section": section.section,
        "contenu": section.contenu,
    }, ensure_ascii=False, indent=2)


def _get_fiche_section(chapitre_num: int, section_num: int) -> str:
    fiche = FicheSection.objects.get(
        chapitre_numero=chapitre_num,
        section_numero=section_num,
    )
    return json.dumps({
        "chapitre": fiche.chapitre_numero,
        "section": fiche.section_numero,
        "these_centrale": fiche.these_centrale,
        "arguments_cles": fiche.arguments_cles,
        "concepts_introduits": fiche.concepts_introduits,
        "liens_chapitres": fiche.liens_chapitres,
        "a_ne_pas_repeter": fiche.a_ne_pas_repeter,
        "ton_angle": fiche.ton_angle,
        "_raw": fiche.raw,
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Registre des concepts (depuis BDD)
# ---------------------------------------------------------------------------

def _iter_previous_sections(
    chapitre: int, section: int, structure_data: list[dict]
) -> list[tuple[int, int]]:
    previous: list[tuple[int, int]] = []
    for chap in structure_data:
        chap_num = int(chap.get("numero", 0))
        for sec in chap.get("sections", []):
            sec_num = int(sec.get("numero", 0))
            if chap_num < chapitre or (chap_num == chapitre and sec_num < section):
                previous.append((chap_num, sec_num))
    return sorted(previous)


def _build_previous_concepts_register(chapitre: int, section: int, livre_id: int) -> str:
    if chapitre == 1 and section == 1:
        return "Aucun concept precedent (premiere section du livre)."

    structure_data = json.loads(recup_chapitres_sections(livre_id))
    depth_order = {"survol": 0, "developpe": 1, "central": 2}
    concept_map: dict[str, dict[str, Any]] = {}

    for prev_chapitre, prev_section in _iter_previous_sections(chapitre, section, structure_data):
        try:
            fiche_json = _get_fiche_section(prev_chapitre, prev_section)
            resume_data = json.loads(fiche_json)
        except Exception:
            continue

        if not isinstance(resume_data, dict):
            continue

        for concept in (resume_data.get("concepts_introduits") or []):
            normalized = str(concept).strip()
            if not normalized:
                continue
            existing = concept_map.get(normalized)
            if existing is None or depth_order[existing["profondeur"]] < depth_order["developpe"]:
                concept_map[normalized] = {
                    "chapitre": prev_chapitre,
                    "section": prev_section,
                    "profondeur": "developpe",
                }

        for concept in (resume_data.get("a_ne_pas_repeter") or []):
            normalized = str(concept).strip()
            if not normalized:
                continue
            concept_map[normalized] = {
                "chapitre": prev_chapitre,
                "section": prev_section,
                "profondeur": "central",
            }

        thesis = str(resume_data.get("these_centrale") or "").strip()
        if thesis:
            existing = concept_map.get(thesis)
            if existing is None or depth_order[existing["profondeur"]] < depth_order["central"]:
                concept_map[thesis] = {
                    "chapitre": prev_chapitre,
                    "section": prev_section,
                    "profondeur": "central",
                }

    if not concept_map:
        return "Aucun concept prealablement traite disponible dans les resumes."

    lines = [
        f"{concept} - Section {payload['chapitre']}.{payload['section']} - Profondeur de traitement : {payload['profondeur']}"
        for concept, payload in sorted(concept_map.items())
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Vérifications individuelles
# ---------------------------------------------------------------------------

def verification_artefact_section_report(chapitre: int, section: int, livre_id: int) -> dict[str, Any]:
    prompt = read_text_file(INPUT_DIR / "vas_prompt.txt", "prompt verification artefact", require_non_empty=False)
    section_raw = _get_section_texte(chapitre, section, livre_id)

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_artefact_ch{chapitre}_s{section}",
    )
    return _make_result(chapitre, section, response_text)


def verification_artefact_section(chapitre: int, section: int, livre_id: int) -> bool:
    return verification_artefact_section_report(chapitre, section, livre_id)["decision"] == "OUI"


def verification_fluidite_section_report(chapitre: int, section: int, livre_id: int) -> dict[str, Any]:
    prompt = read_text_file(INPUT_DIR / "vfs_prompt.txt", "prompt verification fluidite", require_non_empty=False)
    fiche_raw = recup_fiche_cadrage(livre_id)
    plan_raw = recup_plan_detail(livre_id)
    structure = recup_chapitres_sections(livre_id)
    section_raw = _get_section_texte(chapitre, section, livre_id)

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"FICHE CADRAGE : {fiche_raw}"
            f"PLAN DETAIL : {plan_raw}"
            f"STRUCTURE : {structure}"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_fluidite_ch{chapitre}_s{section}",
    )
    return _make_result(chapitre, section, response_text)


def verification_fluidite_section(chapitre: int, section: int, livre_id: int) -> bool:
    return verification_fluidite_section_report(chapitre, section, livre_id)["decision"] == "OUI"


def verification_coherence_interne_section_report(chapitre: int, section: int, livre_id: int) -> dict[str, Any]:
    prompt = read_text_file(INPUT_DIR / "vcs_prompt.txt", "prompt verification coherence interne", require_non_empty=False)
    section_raw = _get_section_texte(chapitre, section, livre_id)

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_coherence_interne_ch{chapitre}_s{section}",
    )
    return _make_result(chapitre, section, response_text)


def verification_linguistique_section_report(chapitre: int, section: int, livre_id: int) -> dict[str, Any]:
    prompt = read_text_file(INPUT_DIR / "vls_prompt.txt", "prompt verification linguistique", require_non_empty=False)
    section_raw = _get_section_texte(chapitre, section, livre_id)

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_linguistique_ch{chapitre}_s{section}",
    )
    return _make_result(chapitre, section, response_text)


def verification_redondance_inter_sections_report(chapitre: int, section: int, livre_id: int) -> dict[str, Any]:
    prompt = read_text_file(INPUT_DIR / "vrs_prompt.txt", "prompt verification redondance", require_non_empty=False)
    section_raw = _get_section_texte(chapitre, section, livre_id)
    register = _build_previous_concepts_register(chapitre, section, livre_id)

    if chapitre == 1 and section == 1:
        response_text = "OUI - Pas de section precedente a comparer."
    else:
        response_text = _generate_text_with_retry(
            contents=(
                f"{prompt}\n\n"
                f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}\n\n"
                f"REGISTRE DES CONCEPTS DEJA TRAITES :\n{register}"
            ),
            context_label=f"verification_redondance_inter_sections_ch{chapitre}_s{section}",
        )

    result = _make_result(chapitre, section, response_text, extra={"registre_concepts": register})
    return _normalize_non_actionable_non(result, "redondance_inter_sections")


# ---------------------------------------------------------------------------
# Rapport global
# ---------------------------------------------------------------------------

def verification_section_report(chapitre: int, section: int, livre_id: int) -> dict[str, Any]:
    artefact_report = verification_artefact_section_report(chapitre, section, livre_id)
    fluidite_report = verification_fluidite_section_report(chapitre, section, livre_id)
    coherence_interne_report = verification_coherence_interne_section_report(chapitre, section, livre_id)
    linguistique_report = verification_linguistique_section_report(chapitre, section, livre_id)
    redondance_report = verification_redondance_inter_sections_report(chapitre, section, livre_id)

    decision = "OUI"
    for blocking_report in [artefact_report, fluidite_report, coherence_interne_report, linguistique_report]:
        if blocking_report and blocking_report["decision"] != "OUI":
            decision = blocking_report["decision"]
            break

    alerte_redondance = None
    if redondance_report and redondance_report["decision"] != "OUI":
        alerte_redondance = redondance_report.get("critique")

    return {
        "chapitre": chapitre,
        "section": section,
        "decision": decision,
        "artefact": artefact_report,
        "fluidite": fluidite_report,
        "coherence_interne": coherence_interne_report,
        "linguistique": linguistique_report,
        "redondance_inter_sections": redondance_report,
        "alerte_redondance_inter_sections": alerte_redondance,
        "redondance_inter_sections_bloquante": False,
        "critique_artefact": artefact_report.get("critique"),
        "critique_fluidite": (fluidite_report or {}).get("critique"),
        "critique_coherence_interne": (coherence_interne_report or {}).get("critique"),
        "critique_linguistique": (linguistique_report or {}).get("critique"),
        "critique_redondance_inter_sections": (redondance_report or {}).get("critique"),
    }


def verification_section(chapitre: int, section: int, livre_id: int) -> bool:
    return verification_section_report(chapitre, section, livre_id)["decision"] == "OUI"