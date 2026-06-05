import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from ...settings import BASE_DIR
from ...models import (
    ChapitreDetails,
    FicheSection,
    ProcessStatus,
    ResumeSection,
    SectionDetaillee,
    SectionTexte,
)
from ..check import check_book_progress, get_resume_instructions
from ..fiche_cadrage import recup_fiche_cadrage
from ..parser import parse_resume, parse_section, read_text_file
from ..plan_detaille import recup_plan_detail
from ..structure_chapitre import recup_chapitres_sections
from .section_cleaner import normalize_section_content, strip_leading_title
from .section_verification import verification_section_report as run_section_verification_report

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
MAX_BOOK_WORDS = 15000
SECTION_WORD_RANGE = 300
MAX_SECTION_REGEN_ATTEMPTS = 20
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
    raise RuntimeError(f"Echec de generation Gemini ({context_label}).")


# ---------------------------------------------------------------------------
# Structure helpers
# ---------------------------------------------------------------------------

def load_structure(livre_id: int) -> list[dict]:
    data = json.loads(recup_chapitres_sections(livre_id))
    if not isinstance(data, list):
        raise ValueError("La structure des chapitres doit etre une liste.")
    return data


def _find_section_title(chapitre: int, section: int, livre_id: int) -> str | None:
    for chap in load_structure(livre_id):
        if int(chap.get("numero", 0)) != chapitre:
            continue
        for sec in chap.get("sections", []):
            if int(sec.get("numero", 0)) == section:
                title = sec.get("titre_section")
                if isinstance(title, str) and title.strip():
                    return title.strip()
    return None


def _count_words(text: str) -> int:
    return len(re.findall(r"[\wÀ-ÖØ-öø-ÿ]+(?:[''-][\wÀ-ÖØ-öø-ÿ]+)*", text, flags=re.UNICODE))


def _count_total_sections(chapitres: list[dict]) -> int:
    return sum(len(chap.get("sections", [])) for chap in chapitres if isinstance(chap, dict))


def _compute_section_word_bounds(total_sections: int) -> tuple[int, int, int]:
    if total_sections <= 0:
        raise ValueError("Impossible de calculer les bornes: nombre total de sections invalide.")
    target_words = max(1, round(MAX_BOOK_WORDS / total_sections))
    half_range = max(1, SECTION_WORD_RANGE // 2)
    min_words = max(1, target_words - half_range)
    max_words = max(min_words, target_words + half_range)
    return min_words, max_words, target_words


def _parse_mots_cible_range(raw_value) -> tuple[int, int] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        value = max(1, raw_value)
        return value, value
    if isinstance(raw_value, dict):
        min_raw = raw_value.get("min")
        max_raw = raw_value.get("max")
        if min_raw is None or max_raw is None:
            return None
        return max(1, int(min_raw)), max(1, int(max_raw))
    if isinstance(raw_value, str):
        text = raw_value.strip().replace("–", "-").replace("—", "-").replace("−", "-")
        if not text:
            return None
        if re.fullmatch(r"\d+", text):
            value = max(1, int(text))
            return value, value
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text)
        if m:
            min_words = max(1, int(m.group(1)))
            return min_words, max(min_words, int(m.group(2)))
    return None


def _resolve_section_word_bounds(
    chapitre: int, section: int, structure_data: list[dict]
) -> tuple[int, int, int, str]:
    for chap in structure_data:
        if not isinstance(chap, dict):
            continue
        if int(chap.get("numero", 0)) != chapitre:
            continue
        for sec in chap.get("sections", []):
            if not isinstance(sec, dict):
                continue
            if int(sec.get("numero", 0)) != section:
                continue

            section_range = _parse_mots_cible_range(sec.get("mots_cible"))
            raw_target = sec.get("nombre_mots_section")
            target_words = None
            if raw_target not in (None, ""):
                try:
                    target_words = max(1, int(raw_target))
                except (TypeError, ValueError):
                    pass

            if section_range:
                min_words, max_words = section_range
                if target_words is None:
                    target_words = round((min_words + max_words) / 2)
                else:
                    target_words = max(min_words, min(max_words, target_words))
                return min_words, max_words, target_words, "structure_chapitre"

            if target_words is not None:
                half_range = max(1, SECTION_WORD_RANGE // 2)
                min_words = max(1, target_words - half_range)
                max_words = max(min_words, target_words + half_range)
                return min_words, max_words, target_words, "structure_chapitre"

            break

    total_sections = _count_total_sections(structure_data)
    min_words, max_words, target_words = _compute_section_word_bounds(total_sections)
    return min_words, max_words, target_words, "fallback_global"


# ---------------------------------------------------------------------------
# Coherence context (depuis BDD)
# ---------------------------------------------------------------------------

def _iter_previous_sections(
    chapitre: int, section: int, structure_data: list[dict]
) -> list[tuple[int, int]]:
    previous: list[tuple[int, int]] = []
    for chap in structure_data:
        if not isinstance(chap, dict):
            continue
        chap_num = int(chap.get("numero", 0))
        for sec in chap.get("sections", []):
            if not isinstance(sec, dict):
                continue
            sec_num = int(sec.get("numero", 0))
            if chap_num < chapitre or (chap_num == chapitre and sec_num < section):
                previous.append((chap_num, sec_num))
    return sorted(previous)


def _load_previous_coherence_context(
    chapitre: int, section: int, structure_data: list[dict], livre_id
) -> str:
    previous_sections = _iter_previous_sections(chapitre, section, structure_data)
    if not previous_sections:
        return "Aucun contexte precedent (premiere section du livre)."

    for prev_chapitre, prev_section in reversed(previous_sections):
        try:
            fiche_json = recup_fiche_section(prev_chapitre, prev_section, livre_id)
            resume_data = json.loads(fiche_json)
        except Exception:
            continue

        if not isinstance(resume_data, dict):
            continue

        these = str(resume_data.get("these_centrale") or "").strip()
        arguments = resume_data.get("arguments_cles") or []
        concepts = resume_data.get("concepts_introduits") or []
        no_repeat = resume_data.get("a_ne_pas_repeter") or []

        argument_line = "; ".join(str(a).strip() for a in arguments if str(a).strip())
        concept_line = "; ".join(str(c).strip() for c in concepts if str(c).strip())
        no_repeat_line = "; ".join(str(n).strip() for n in no_repeat if str(n).strip())

        parts = [f"Reference precedente: chapitre {prev_chapitre}, section {prev_section}."]
        if these:
            parts.append(f"These centrale: {these}")
        if argument_line:
            parts.append(f"Arguments cles: {argument_line}")
        if concept_line:
            parts.append(f"Concepts introduits: {concept_line}")
        if no_repeat_line:
            parts.append(f"A ne pas repeter: {no_repeat_line}")

        return "\n".join(parts)

    return "Aucun resume precedent exploitable trouve."


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def gen_section(chapitre: int, section: int, livre_id: int, verification_section: bool = True):
    chapitre = int(chapitre)
    section = int(section)

    fiche = recup_fiche_cadrage(livre_id)
    plan = recup_plan_detail(livre_id)
    structure = recup_chapitres_sections(livre_id)

    prompt_path = INPUT_DIR / "s_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt section", require_non_empty=False)

    structure_data = load_structure(livre_id)
    min_words, max_words, target_words, bounds_source = _resolve_section_word_bounds(
        chapitre, section, structure_data
    )
    if bounds_source == "structure_chapitre":
        print(f"Contraintes section depuis structure_chapitre: cible {target_words} mots, plage {min_words}-{max_words}.")
    else:
        total_sections = _count_total_sections(structure_data)
        print(
            f"[WARN] Contraintes absentes dans structure_chapitre pour ch{chapitre}s{section}. "
            f"Fallback global: cible {target_words} mots, plage {min_words}-{max_words} "
            f"(total sections: {total_sections}, max livre: {MAX_BOOK_WORDS})."
        )

    coherence_text = _load_previous_coherence_context(chapitre, section, structure_data, livre_id)

    # Phase 1 : jet d'essai
    try:
        _run_section_generation_phase(
            chapitre, section, livre_id,
            prompt, fiche, plan, structure,
            coherence_text, min_words, max_words, target_words,
            verification_section,
            phase_label="jet_essai",
            max_attempts=MAX_SECTION_REGEN_ATTEMPTS,
        )
        return
    except Exception as err:
        print(
            f"[WARN] Jet d'essai echoue pour section_ch{chapitre}_s{section}: {err}. "
            "Nouvelle passe avec le prompt du jet d'essai."
        )

    # Phase 2 : retry apres erreur
    _run_section_generation_phase(
        chapitre, section, livre_id,
        prompt, fiche, plan, structure,
        coherence_text, min_words, max_words, target_words,
        verification_section,
        phase_label="retry_apres_erreur",
        max_attempts=MAX_SECTION_REGEN_ATTEMPTS,
    )


def _run_section_generation_phase(
    chapitre: int,
    section: int,
    livre_id: int,
    prompt: str,
    fiche: str,
    plan: str,
    structure: str,
    coherence_text: str,
    min_words: int,
    max_words: int,
    target_words: int,
    verification_section: bool,
    phase_label: str,
    max_attempts: int,
) -> None:
    critique_artefact_feedback = ""
    critique_fluidite_feedback = ""
    critique_coherence_interne_feedback = ""
    critique_linguistique_feedback = ""
    critique_redondance_inter_sections_feedback = ""

    for regen_attempt in range(1, max_attempts + 1):
        critique_block = ""
        if any([
            critique_artefact_feedback,
            critique_fluidite_feedback,
            critique_coherence_interne_feedback,
            critique_linguistique_feedback,
            critique_redondance_inter_sections_feedback,
        ]):
            critique_block = "\n\nRETOURS CRITIQUES DE VERIFICATION (obligatoire a corriger):\n"
            if critique_artefact_feedback:
                critique_block += f"- Artefact:\n{critique_artefact_feedback}\n"
            if critique_fluidite_feedback:
                critique_block += f"- Fluidite:\n{critique_fluidite_feedback}\n"
            if critique_coherence_interne_feedback:
                critique_block += f"- Coherence interne:\n{critique_coherence_interne_feedback}\n"
            if critique_linguistique_feedback:
                critique_block += f"- Linguistique:\n{critique_linguistique_feedback}\n"
            if critique_redondance_inter_sections_feedback:
                critique_block += f"- Redondance inter-sections:\n{critique_redondance_inter_sections_feedback}\n"
            critique_block += "Corrige explicitement tous ces points dans cette nouvelle version de la section."

        response_text = _generate_text_with_retry(
            contents=(
                f"{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\n"
                f"FICHE DE STRUCTURE DU CHAPITRE : {structure}\n\n"
                f"CHAPITRE À RÉDIGER : Chapitre {chapitre}\n\n"
                f"SECTION À RÉDIGER : Section {section}\n\n"
                f"CONTRAINTE DE LONGUEUR : vise environ {target_words} mots, accepte uniquement "
                f"une section entre {min_words} et {max_words} mots. "
                f"Critiques à prendre en considération : {critique_block}\n\n"
                f"Vérification de cohérence avec la section précédente : {coherence_text}"
            ),
            context_label=f"section_ch{chapitre}_s{section}",
        )

        parsed = parse_section(response_text, chapitre, section)
        if not isinstance(parsed, dict):
            raise ValueError(f"Section parsee invalide pour ch{chapitre} s{section} (phase {phase_label}).")
        if not isinstance(parsed.get("contenu"), str) or not parsed.get("contenu", "").strip():
            raise ValueError(f"Contenu de section vide apres parsing pour ch{chapitre} s{section} (phase {phase_label}).")

        # Nettoyage du titre en tête de contenu
        section_title = _find_section_title(chapitre, section, livre_id)
        if section_title and isinstance(parsed.get("contenu"), str):
            cleaned_content, removed, matched_separator = strip_leading_title(parsed["contenu"], section_title)
            if removed:
                parsed["contenu"] = cleaned_content
                print(f"Prefixe titre retire pour section_ch{chapitre}_s{section} ({matched_separator!r}).")

        ajout_section_texte(parsed, livre_id)

        contenu = normalize_section_content(parsed.get("contenu", ""))
        word_count = _count_words(contenu)
        print(f"Section {section} du chapitre {chapitre} sauvegardee ({word_count} mots).")

        if min_words <= word_count <= max_words:
            if verification_section:
                verification_report = run_section_verification_report(chapitre, section, livre_id)
                verification_ok = verification_report.get("decision") == "OUI"
                if not verification_ok:
                    critique_artefact_feedback = str(verification_report.get("critique_artefact") or "").strip()
                    critique_fluidite_feedback = str(verification_report.get("critique_fluidite") or "").strip()
                    critique_coherence_interne_feedback = str(verification_report.get("critique_coherence_interne") or "").strip()
                    critique_linguistique_feedback = str(verification_report.get("critique_linguistique") or "").strip()
                    critique_redondance_inter_sections_feedback = str(verification_report.get("critique_redondance_inter_sections") or "").strip()
                    if regen_attempt == max_attempts:
                        raise RuntimeError(
                            f"Section section_ch{chapitre}_s{section} invalidee par verification apres {max_attempts} tentatives (phase {phase_label})."
                        )
                    print(
                        f"Section section_ch{chapitre}_s{section} invalidee par verification (NON). "
                        f"Regeneration {phase_label} ({regen_attempt}/{max_attempts})..."
                    )
                    if critique_artefact_feedback:
                        print(f"  [critique_artefact] {critique_artefact_feedback}")
                    if critique_fluidite_feedback:
                        print(f"  [critique_fluidite] {critique_fluidite_feedback}")
                    if critique_coherence_interne_feedback:
                        print(f"  [critique_coherence_interne] {critique_coherence_interne_feedback}")
                    if critique_linguistique_feedback:
                        print(f"  [critique_linguistique] {critique_linguistique_feedback}")
                    if critique_redondance_inter_sections_feedback:
                        print(f"  [critique_redondance] {critique_redondance_inter_sections_feedback}")
                    continue

                coherence_check(chapitre, section, livre_id)
                print(
                    f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). "
                    "Verification (OUI) et coherence effectuees."
                )
            else:
                print(
                    f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). "
                    "verification_section desactivee."
                )
            return

        if regen_attempt == max_attempts:
            raise RuntimeError(
                f"Section section_ch{chapitre}_s{section} hors plage ({word_count} mots, "
                f"attendu {min_words}-{max_words}, cible {target_words}) apres {max_attempts} tentatives (phase {phase_label})."
            )

        length_issue = "trop courte" if word_count < min_words else "trop longue"
        print(
            f"Section section_ch{chapitre}_s{section} {length_issue} ({word_count} mots, "
            f"attendu {min_words}-{max_words}, cible {target_words}). "
            f"Regeneration {phase_label} ({regen_attempt}/{max_attempts})..."
        )


def coherence_check(chapitre: int, section: int, livre_id: int):
    chapitre = int(chapitre)
    section = int(section)

    section_json = recup_section_texte(chapitre, section, livre_id)

    prompt_path = INPUT_DIR / "c_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt coherence", require_non_empty=False)

    response_text = _generate_text_with_retry(
        contents=f"{prompt}\n\nSection à étudier :{section_json}",
        context_label=f"coherence_ch{chapitre}_s{section}",
    )

    parsed = parse_resume(response_text, chapitre, section)
    if not isinstance(parsed, dict):
        raise ValueError(f"Resume parse invalide pour ch{chapitre} s{section}: objet JSON attendu.")

    ajout_fiche_section(parsed, livre_id)
    return parsed


# ---------------------------------------------------------------------------
# suivisection
# ---------------------------------------------------------------------------

def _normalize_resume_from(resume_from):
    if not isinstance(resume_from, dict):
        return None
    try:
        return {"chapitre": int(resume_from.get("chapitre")), "section": int(resume_from.get("section"))}
    except (TypeError, ValueError):
        return None


def _find_start_indices(chapitres: list, start_from) -> tuple[int, int]:
    if not start_from:
        return 0, 0
    target = _normalize_resume_from(start_from)
    if not target:
        print("Point de reprise invalide, reprise depuis le debut des sections.")
        return 0, 0
    for chap_idx, chap in enumerate(chapitres):
        if int(chap["numero"]) != target["chapitre"]:
            continue
        for sec_idx, sec in enumerate(chap.get("sections", [])):
            if int(sec["numero"]) == target["section"]:
                return chap_idx, sec_idx
    print("Point de reprise introuvable dans la structure, reprise depuis le debut.")
    return 0, 0


def _infer_start_from_generated_sections(livre_id: int):
    progress = check_book_progress()
    reprise = progress.get("reprise", {})
    if reprise.get("next_function") == "gen_all_sections" and reprise.get("resume_from"):
        return reprise.get("resume_from")
    missing_sections = progress.get("manquants", {}).get("sections_brutes", [])
    if missing_sections:
        return missing_sections[0]
    missing_resumes = progress.get("manquants", {}).get("resumes_coherence", [])
    if missing_resumes:
        return missing_resumes[0]
    return None

def reprise_generation(livre_id: int):
    """
    Cherche la dernière section générée en BDD et reprend la génération
    à partir de celle-ci (en la régénérant).
    """
    derniere = (
        SectionTexte.objects
        .filter(livre_id=livre_id)
        .order_by("-chapitre", "-section")
        .first()
    )

    if derniere is None:
        print("Aucune section trouvée en BDD, génération depuis le début.")
        suivisection(livre_id)
        return

    print(
        f"Dernière section trouvée : chapitre {derniere.chapitre}, "
        f"section {derniere.section}. Reprise depuis ce point."
    )

    # Supprimer la dernière section pour la régénérer proprement
    derniere.delete()

    suivisection(livre_id, start_from={
        "chapitre": derniere.chapitre,
        "section": derniere.section,
    })

def suivisection(livre_id: int, start_from=None, auto_confirm=False):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    chapitres = load_structure(livre_id)
    nb_chapitres = len(chapitres)
    nb_total_sections = sum(len(ch["sections"]) for ch in chapitres)
    print(f"Structure chargee : {nb_chapitres} chapitres, {nb_total_sections} sections au total\n")

    if start_from is None:
        start_from = _infer_start_from_generated_sections(livre_id)
        if start_from:
            print(f"Reprise detectee depuis les sections generees: {start_from}")

    chap_idx, sec_start_idx = _find_start_indices(chapitres, start_from)
    start_chap_idx = chap_idx

    if start_from and (chap_idx != 0 or sec_start_idx != 0):
        print(
            f"Reprise fine activee depuis chapitre {chapitres[chap_idx]['numero']} "
            f"section {chapitres[chap_idx]['sections'][sec_start_idx]['numero']}."
        )

    while chap_idx < nb_chapitres:
        chap = chapitres[chap_idx]
        ch_num = int(chap["numero"])
        nb_sec = len(chap["sections"])
        print(f"Chapitre {ch_num} — {chap['titre']} ({nb_sec} sections)")

        start_idx_for_chapter = sec_start_idx if chap_idx == start_chap_idx else 0
        for sec in chap["sections"][start_idx_for_chapter:]:
            sec_num = int(sec["numero"])
            status.message = f"Generation section ch{ch_num} s{sec_num}..."
            status.save()
            print(f"Generation de la section {sec_num} du chapitre {ch_num}...")
            gen_section(ch_num, sec_num, livre_id)

        chap_idx += 1


# ---------------------------------------------------------------------------
# merge (adapté BDD)
# ---------------------------------------------------------------------------

def merge_chapter_sections(chapitre_num: int, livre_id: int) -> dict:
    chapitre_num = int(chapitre_num)
    structure_data = load_structure(livre_id)

    chapitre_data = None
    for chap in structure_data:
        if int(chap.get("numero", 0)) == chapitre_num:
            chapitre_data = chap
            break

    if chapitre_data is None:
        print(f"Chapitre {chapitre_num} introuvable dans la structure.")
        return {}

    sections = []
    for sec in chapitre_data.get("sections", []):
        sec_num = int(sec.get("numero", 0))
        try:
            section_json = recup_section_texte(chapitre_num, sec_num, livre_id)
            data = json.loads(section_json)
        except Exception as err:
            print(f"Section ch{chapitre_num} s{sec_num} introuvable en BDD: {err}")
            continue

        sections.append({
            "section": sec_num,
            "titre": sec.get("titre_section", ""),
            "contenu": normalize_section_content(data.get("contenu", "")),
        })

    result = {
        "chapitre": chapitre_num,
        "titre": chapitre_data.get("titre", ""),
        "nb_sections": len(sections),
        "sections": sections,
    }

    print(f"Chapitre {chapitre_num} fusionne ({len(sections)} sections).")
    return result


def merge_all_chapters(livre_id: int) -> list[dict]:
    chapitres = load_structure(livre_id)
    print(f"Fusion des sections pour {len(chapitres)} chapitres...\n")
    result = []
    for chap in chapitres:
        result.append(merge_chapter_sections(int(chap.get("numero", 0)), livre_id))
    print("\nFusion terminee.")
    return result


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_fiche_section(data: dict, livre_id: int):
    chapitre_num = int(data.get("chapitre"))
    section_num = int(data.get("section"))

    section = SectionDetaillee.objects.get(
        chapitre__numero=chapitre_num,
        numero=section_num,
        livre_id=livre_id
    )

    FicheSection.objects.update_or_create(
        section=section,
        chapitre_numero=chapitre_num,
        section_numero=section_num,
        livre_id=livre_id,
        defaults={
            "these_centrale": data.get("these_centrale"),
            "arguments_cles": data.get("arguments_cles"),
            "concepts_introduits": data.get("concepts_introduits"),
            "a_ne_pas_repeter": data.get("a_ne_pas_repeter"),
            "liens_chapitres": data.get("liens_chapitres"),
            "ton_angle": data.get("ton_angle"),
            "raw": data.get("_raw"),
        },
    )


def ajout_section_texte(data: dict, livre_id: int):
    SectionTexte.objects.update_or_create(
        chapitre=data.get("chapitre"),
        section=data.get("section"),
        livre_id=livre_id,
        defaults={"contenu": data.get("contenu")},
    )


def recup_fiche_section(chapitre_num: int, section_num: int, livre_id : int) -> str:
    fiche = FicheSection.objects.get(
        chapitre_numero=chapitre_num,
        section_numero=section_num,
        livre_id=livre_id
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


def recup_section_texte(chapitre_num: int, section_num: int, livre_id: int) -> str:
    section = SectionTexte.objects.get(chapitre=chapitre_num, section=section_num, livre_id=livre_id)
    return json.dumps({
        "chapitre": section.chapitre,
        "section": section.section,
        "contenu": section.contenu,
    }, ensure_ascii=False, indent=2)


def recup_section_texte_all(livre_id: int) -> list[dict]:
    sections = SectionTexte.objects.filter(livre_id=livre_id).order_by("chapitre", "section")
    chapitres_struct = ChapitreDetails.objects.prefetch_related("sections").filter(livre_id=livre_id)

    titres = {}
    for chap in chapitres_struct:
        for sec in chap.sections.all():
            titres[(int(chap.numero), int(sec.numero))] = {
                "titre_chapitre": chap.titre,
                "titre_section": sec.titre_section,
            }

    result = []
    for s in sections:
        key = (int(s.chapitre), int(s.section))
        info = titres.get(key, {})
        result.append({
            "chapitre": s.chapitre,
            "section": s.section,
            "titre_chapitre": info.get("titre_chapitre"),
            "titre_section": info.get("titre_section"),
            "contenu": s.contenu,
        })
    return result


def reset_section_texte(livre_id: int):
    SectionTexte.objects.filter(livre_id=livre_id).delete()


def reset_resume_section(livre_id: int):
    ResumeSection.objects.filter(livre_id=livre_id).delete()


def reset_fiche_section(livre_id: int):
    FicheSection.objects.filter(livre_id=livre_id).delete()


def reset_all_test(livre_id: int):
    reset_section_texte(livre_id)
    reset_resume_section(livre_id)
    reset_fiche_section(livre_id)