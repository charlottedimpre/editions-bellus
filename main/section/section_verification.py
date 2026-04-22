import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SECTION_DIR = OUTPUT_DIR / "section"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
RESUME_DIR = OUTPUT_DIR / "resume"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier .env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
CLIENT = genai.Client(api_key=GEMINI_API_KEY)


def _generate_text_with_retry(contents: str, context_label: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError(f"Reponse vide de Gemini ({context_label}).")
            return text
        except ServerError as err:
            status_code = getattr(err, "status_code", None)
            is_503 = status_code == 503 or str(err).startswith("503")
            if not is_503:
                raise RuntimeError(
                    f"Erreur serveur Gemini non 503 ({context_label}): {err}"
                ) from err

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Erreur 503 Gemini apres {MAX_RETRIES} tentatives ({context_label})."
                ) from err

            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Aucune reponse exploitable de Gemini ({context_label}).")


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

    # Tente d'extraire le motif immediatement apres "NON", sinon garde la reponse brute.
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
        "aucune correction",
        "aucun correctif",
        "pas de correction",
        "rien a corriger",
        "rien à corriger",
        "aucune anomalie",
        "aucun probleme",
        "aucun problème",
        "r.a.s",
        "ras",
    ]
    return any(marker in text for marker in markers)


def _normalize_non_actionable_non(result: dict[str, Any], gate_name: str) -> dict[str, Any]:
    normalized = dict(result)
    if normalized.get("decision") != "NON":
        return normalized

    critique = normalized.get("critique")
    if not _is_non_actionable_critique(critique):
        return normalized

    normalized["decision"] = "OUI"
    normalized["critique"] = None
    normalized["normalisation"] = (
        f"{gate_name}: NON non actionnable converti en OUI"
    )
    return normalized


def _save_report(filename: str, payload: dict[str, Any]) -> None:
    # Sortie disque des rapports de verification desactivee.
    _ = (filename, payload)


def verification_artefact_section_report(chapitre: int, section: int) -> dict[str, Any]:
    prompt_path = INPUT_DIR / "vas_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_raw = f.read()

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_artefact_ch{chapitre}_s{section}",
    )
    is_valid = _parse_yes_no(response_text)
    critique = _extract_critique(response_text, is_valid)

    result = {
        "chapitre": chapitre,
        "section": section,
        "decision": "OUI" if is_valid is True else "NON" if is_valid is False else "INDETERMINE",
        "critique": critique,
        "raw": response_text,
    }
    _save_report(f"verification_artefact_ch{chapitre}_s{section}.json", result)
    return result


def verification_artefact_section(chapitre: int, section: int) -> bool:
    result = verification_artefact_section_report(chapitre, section)
    return result["decision"] == "OUI"


def verification_fluidite_section_report(chapitre: int, section: int) -> dict[str, Any]:
    prompt_path = INPUT_DIR / "vfs_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    with FICHE_CADRAGE_PATH.open("r", encoding="utf-8") as f:
        fiche_raw = f.read()

    with PLAN_DETAIL_PATH.open("r", encoding="utf-8") as f:
        plan_raw = f.read()

    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        structure = f.read()

    section_path = SECTION_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_raw = f.read()

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
    is_valid = _parse_yes_no(response_text)
    critique = _extract_critique(response_text, is_valid)

    result = {
        "chapitre": chapitre,
        "section": section,
        "decision": "OUI" if is_valid is True else "NON" if is_valid is False else "INDETERMINE",
        "critique": critique,
        "raw": response_text,
    }
    _save_report(f"verification_fluidite_ch{chapitre}_s{section}.json", result)
    return result

def verification_fluidite_section(chapitre: int, section: int) -> bool:
    result = verification_fluidite_section_report(chapitre, section)
    return result["decision"] == "OUI"


def _iter_previous_sections(chapitre: int, section: int) -> list[tuple[int, int]]:
    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        structure = json.load(f)

    previous_sections: list[tuple[int, int]] = []
    for chap in structure:
        chap_num = int(chap.get("numero", 0))
        for sec in chap.get("sections", []):
            sec_num = int(sec.get("numero", 0))
            if chap_num < chapitre or (chap_num == chapitre and sec_num < section):
                previous_sections.append((chap_num, sec_num))

    return sorted(previous_sections)


def _build_previous_concepts_register(chapitre: int, section: int) -> str:
    if chapitre == 1 and section == 1:
        return "Aucun concept precedent (premiere section du livre)."

    depth_order = {"survol": 0, "developpe": 1, "central": 2}
    concept_map: dict[str, dict[str, Any]] = {}

    for prev_chapitre, prev_section in _iter_previous_sections(chapitre, section):
        resume_path = RESUME_DIR / f"coherence_ch{prev_chapitre}_s{prev_section}.json"
        if not resume_path.exists():
            continue

        try:
            with resume_path.open("r", encoding="utf-8") as f:
                resume_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        concepts_introduits = resume_data.get("concepts_introduits") or []
        for concept in concepts_introduits:
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

        not_to_repeat = resume_data.get("a_ne_pas_repeter") or []
        for concept in not_to_repeat:
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

    lines = []
    for concept, payload in sorted(concept_map.items()):
        lines.append(
            f"{concept} - Section {payload['chapitre']}.{payload['section']} - Profondeur de traitement : {payload['profondeur']}"
        )
    return "\n".join(lines)


def verification_coherence_interne_section_report(chapitre: int, section: int) -> dict[str, Any]:
    prompt_path = INPUT_DIR / "vcs_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_raw = f.read()

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_coherence_interne_ch{chapitre}_s{section}",
    )
    is_valid = _parse_yes_no(response_text)
    critique = _extract_critique(response_text, is_valid)

    result = {
        "chapitre": chapitre,
        "section": section,
        "decision": "OUI" if is_valid is True else "NON" if is_valid is False else "INDETERMINE",
        "critique": critique,
        "raw": response_text,
    }
    _save_report(f"verification_coherence_interne_ch{chapitre}_s{section}.json", result)
    return result


def verification_linguistique_section_report(chapitre: int, section: int) -> dict[str, Any]:
    prompt_path = INPUT_DIR / "vls_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_raw = f.read()

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION A VERIFIER (chapitre {chapitre}, section {section}) :{section_raw}"
        ),
        context_label=f"verification_linguistique_ch{chapitre}_s{section}",
    )
    is_valid = _parse_yes_no(response_text)
    critique = _extract_critique(response_text, is_valid)

    result = {
        "chapitre": chapitre,
        "section": section,
        "decision": "OUI" if is_valid is True else "NON" if is_valid is False else "INDETERMINE",
        "critique": critique,
        "raw": response_text,
    }
    _save_report(f"verification_linguistique_ch{chapitre}_s{section}.json", result)
    return result


def verification_redondance_inter_sections_report(chapitre: int, section: int) -> dict[str, Any]:
    prompt_path = INPUT_DIR / "vrs_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_raw = f.read()

    register = _build_previous_concepts_register(chapitre, section)

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

    is_valid = _parse_yes_no(response_text)
    critique = _extract_critique(response_text, is_valid)

    result = {
        "chapitre": chapitre,
        "section": section,
        "decision": "OUI" if is_valid is True else "NON" if is_valid is False else "INDETERMINE",
        "critique": critique,
        "registre_concepts": register,
        "raw": response_text,
    }
    result = _normalize_non_actionable_non(result, "redondance_inter_sections")
    _save_report(f"verification_redondance_inter_sections_ch{chapitre}_s{section}.json", result)
    return result


def verification_section_report(chapitre: int, section: int) -> dict[str, Any]:
    artefact_report = verification_artefact_section_report(chapitre, section)
    fluidite_report = verification_fluidite_section_report(chapitre, section)
    coherence_interne_report = verification_coherence_interne_section_report(chapitre, section)
    linguistique_report = verification_linguistique_section_report(chapitre, section)
    redondance_inter_sections_report = verification_redondance_inter_sections_report(chapitre, section)

    decision = "OUI"
    for blocking_report in [
        artefact_report,
        fluidite_report,
        coherence_interne_report,
        linguistique_report,
    ]:
        if blocking_report and blocking_report["decision"] != "OUI":
            decision = blocking_report["decision"]
            break

    alerte_redondance = None
    if redondance_inter_sections_report and redondance_inter_sections_report["decision"] != "OUI":
        alerte_redondance = redondance_inter_sections_report.get("critique")

    report = {
        "chapitre": chapitre,
        "section": section,
        "decision": decision,
        "artefact": artefact_report,
        "fluidite": fluidite_report,
        "coherence_interne": coherence_interne_report,
        "linguistique": linguistique_report,
        "redondance_inter_sections": redondance_inter_sections_report,
        "alerte_redondance_inter_sections": alerte_redondance,
        "redondance_inter_sections_bloquante": False,
        "critique_artefact": artefact_report.get("critique"),
        "critique_fluidite": (fluidite_report or {}).get("critique"),
        "critique_coherence_interne": (coherence_interne_report or {}).get("critique"),
        "critique_linguistique": (linguistique_report or {}).get("critique"),
        "critique_redondance_inter_sections": (redondance_inter_sections_report or {}).get("critique"),
    }
    _save_report(f"verification_ch{chapitre}_s{section}.json", report)
    return report


def verification_section(chapitre: int, section: int) -> bool:
    report = verification_section_report(chapitre, section)
    return report["decision"] == "OUI"

if __name__ == '__main__':
    verification_section(1, 4)
