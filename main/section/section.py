import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from parser import (
    parse_resume,
    parse_section,
    read_json_file as _read_json,
    read_text_file as _read_text,
    to_int_or_raise as _to_int,
    write_json_file as _write_json,
)
try:
    from section.section_cleaner import normalize_section_content, strip_leading_title
    from section.section_verification import verification_section_report as run_section_verification_report
except ModuleNotFoundError:
    from section_cleaner import normalize_section_content, strip_leading_title
    from section_verification import verification_section_report as run_section_verification_report

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SECTION_DIR = OUTPUT_DIR / "section"
SECTION_FR_DIR = OUTPUT_DIR / "section_fr"
RESUME_DIR = OUTPUT_DIR / "resume"
CHAPITRE_DIR = OUTPUT_DIR / "chapitre"
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
FICHE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"

load_dotenv(ROOT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier .env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BOOK_WORDS = 15000
SECTION_WORD_RANGE = 300
MAX_SECTION_REGEN_ATTEMPTS = 20
CLIENT = genai.Client(api_key=GEMINI_API_KEY)

SECTION_DIR.mkdir(parents=True, exist_ok=True)
RESUME_DIR.mkdir(parents=True, exist_ok=True)
CHAPITRE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_text_with_retry(contents: str, context_label: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )
            text: str = (response.text or "").strip()
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
                f"Gemini indisponible (503) [{context_label}] tentative {attempt}/{MAX_RETRIES}, nouvelle tentative dans {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Echec de generation Gemini ({context_label}).")


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    structure = _read_json(STRUCTURE_PATH, "structure des chapitres")
    if not isinstance(structure, list):
        raise ValueError("La structure des chapitres doit etre une liste.")
    return structure


def _find_section_title(chapitre: int, section: int) -> str | None:
    for chap in load_structure():
        if not isinstance(chap, dict):
            continue
        try:
            chapitre_num = _to_int(chap.get("numero", 0), "chapitre.numero")
        except ValueError:
            continue
        if chapitre_num != chapitre:
            continue
        for sec in chap.get("sections", []):
            if not isinstance(sec, dict):
                continue
            try:
                section_num = _to_int(sec.get("numero", 0), "section.numero")
            except ValueError:
                continue
            if section_num == section:
                title = sec.get("titre_section")
                if isinstance(title, str) and title.strip():
                    return title.strip()
    return None


def _count_words(text: str) -> int:
    # Compte les mots en preservant les apostrophes/tirets dans les tokens.
    return len(re.findall(r"[\wÀ-ÖØ-öø-ÿ]+(?:['’-][\wÀ-ÖØ-öø-ÿ]+)*", text, flags=re.UNICODE))


def _count_content_words_from_file(filepath: Path) -> int:
    section_data = _read_json(filepath, "section redigee")
    if not isinstance(section_data, dict):
        raise ValueError(f"Format invalide pour section redigee: {filepath}")
    content = normalize_section_content(section_data.get("contenu", ""))
    return _count_words(content)


def _compute_section_word_bounds(total_sections: int) -> tuple[int, int, int]:
    if total_sections <= 0:
        raise ValueError("Impossible de calculer les bornes: nombre total de sections invalide.")

    target_words = max(1, round(MAX_BOOK_WORDS / total_sections))
    half_range = max(1, SECTION_WORD_RANGE // 2)
    min_words = max(1, target_words - half_range)
    max_words = max(min_words, target_words + half_range)
    return min_words, max_words, target_words


def _count_total_sections(chapitres: list[dict]) -> int:
    return sum(len(chap.get("sections", [])) for chap in chapitres if isinstance(chap, dict))


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
        min_words = max(1, int(min_raw))
        max_words = max(min_words, int(max_raw))
        return min_words, max_words

    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None

        # Supporte les variantes de tirets Unicode courantes.
        text = text.replace("–", "-").replace("—", "-").replace("−", "-")

        exact_int = re.fullmatch(r"\d+", text)
        if exact_int:
            value = max(1, int(text))
            return value, value

        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text)
        if range_match:
            min_words = max(1, int(range_match.group(1)))
            max_words = max(min_words, int(range_match.group(2)))
            return min_words, max_words

    return None


def _resolve_section_word_bounds(
    chapitre: int,
    section: int,
    structure_data: list[dict],
) -> tuple[int, int, int, str]:
    for chap in structure_data:
        if not isinstance(chap, dict):
            continue
        try:
            chapitre_num = _to_int(chap.get("numero", 0), "chapitre.numero")
        except ValueError:
            continue
        if chapitre_num != chapitre:
            continue

        sections = chap.get("sections", [])
        if not isinstance(sections, list):
            break

        for sec in sections:
            if not isinstance(sec, dict):
                continue
            try:
                section_num = _to_int(sec.get("numero", 0), "section.numero")
            except ValueError:
                continue
            if section_num != section:
                continue

            section_range = _parse_mots_cible_range(sec.get("mots_cible"))

            target_words = None
            raw_target = sec.get("nombre_mots_section")
            if raw_target not in (None, ""):
                try:
                    target_words = max(1, int(raw_target))
                except (TypeError, ValueError):
                    target_words = None

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


def _iter_previous_sections(
    chapitre: int,
    section: int,
    structure_data: list[dict],
) -> list[tuple[int, int]]:
    previous_sections: list[tuple[int, int]] = []
    for chap in structure_data:
        if not isinstance(chap, dict):
            continue
        try:
            chap_num = _to_int(chap.get("numero", 0), "chapitre.numero")
        except ValueError:
            continue

        sections = chap.get("sections", [])
        if not isinstance(sections, list):
            continue

        for sec in sections:
            if not isinstance(sec, dict):
                continue
            try:
                sec_num = _to_int(sec.get("numero", 0), "section.numero")
            except ValueError:
                continue

            if chap_num < chapitre or (chap_num == chapitre and sec_num < section):
                previous_sections.append((chap_num, sec_num))

    return sorted(previous_sections)


def _load_previous_coherence_context(
    chapitre: int,
    section: int,
    structure_data: list[dict],
) -> str:
    previous_sections = _iter_previous_sections(chapitre, section, structure_data)
    if not previous_sections:
        return "Aucun contexte precedent (premiere section du livre)."

    for prev_chapitre, prev_section in reversed(previous_sections):
        resume_path = RESUME_DIR / f"coherence_ch{prev_chapitre}_s{prev_section}.json"
        if not resume_path.exists():
            continue

        try:
            resume_data = _read_json(resume_path, "resume coherence precedent")
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

        if len(parts) == 1:
            return parts[0]
        return "\n".join(parts)

    return "Aucun resume precedent exploitable trouve."


def gen_section(chapitre, section, verification_section: bool = True):
    chapitre = _to_int(chapitre, "chapitre")
    section = _to_int(section, "section")

    _read_json(FICHE_PATH, "fiche de cadrage")
    fiche = _read_text(FICHE_PATH, "fiche de cadrage")

    _read_json(PLAN_PATH, "plan detaille")
    plan = _read_text(PLAN_PATH, "plan detaille")

    _read_json(STRUCTURE_PATH, "structure chapitre")
    structure = _read_text(STRUCTURE_PATH, "structure chapitre")

    prompt_path = INPUT_DIR / "s_prompt.txt"
    prompt = _read_text(prompt_path, "prompt section")

    structure_data = load_structure()
    min_words, max_words, target_words, bounds_source = _resolve_section_word_bounds(
        chapitre, section, structure_data
    )
    if bounds_source == "structure_chapitre":
        print(
            f"Contraintes section depuis structure_chapitre: cible {target_words} mots, plage {min_words}-{max_words}."
        )
    else:
        total_sections = _count_total_sections(structure_data)
        print(
            f"[WARN] Contraintes absentes dans structure_chapitre pour ch{chapitre}s{section}. "
            f"Fallback global: cible {target_words} mots, plage {min_words}-{max_words} "
            f"(total sections: {total_sections}, max livre: {MAX_BOOK_WORDS})."
        )

    coherence = _load_previous_coherence_context(chapitre, section, structure_data)

    coherence_text = coherence if coherence else ""

    # Phase 1: jet d'essai avec retours de verification.
    try:
        _run_section_generation_phase(
            chapitre,
            section,
            prompt,
            fiche,
            plan,
            structure,
            coherence_text,
            min_words,
            max_words,
            target_words,
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

    # Phase 2: retry apres erreur, re-initialise les critiques.
    _run_section_generation_phase(
        chapitre,
        section,
        prompt,
        fiche,
        plan,
        structure,
        coherence_text,
        min_words,
        max_words,
        target_words,
        verification_section,
        phase_label="retry_apres_erreur",
        max_attempts=MAX_SECTION_REGEN_ATTEMPTS,
    )


def _run_section_generation_phase(
    chapitre: int,
    section: int,
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
    # Retours critiques reinitialises a chaque phase.
    critique_artefact_feedback = ""
    critique_fluidite_feedback = ""
    critique_coherence_interne_feedback = ""
    critique_linguistique_feedback = ""
    critique_redondance_inter_sections_feedback = ""

    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename

    for regen_attempt in range(1, max_attempts + 1):
        critique_block = ""
        if (
            critique_artefact_feedback
            or critique_fluidite_feedback
            or critique_coherence_interne_feedback
            or critique_linguistique_feedback
            or critique_redondance_inter_sections_feedback
        ):
            critique_block = "\n\nRETOURS CRITIQUES DE VERIFICATION (obligatoire a corriger):\n"
            if critique_artefact_feedback:
                critique_block += (
                    "- Artefact:\n"
                    f"{critique_artefact_feedback}\n"
                )
            if critique_fluidite_feedback:
                critique_block += (
                    "- Fluidite:\n"
                    f"{critique_fluidite_feedback}\n"
                )
            if critique_coherence_interne_feedback:
                critique_block += (
                    "- Coherence interne:\n"
                    f"{critique_coherence_interne_feedback}\n"
                )
            if critique_linguistique_feedback:
                critique_block += (
                    "- Linguistique:\n"
                    f"{critique_linguistique_feedback}\n"
                )
            if critique_redondance_inter_sections_feedback:
                critique_block += (
                    "- Redondance inter-sections:\n"
                    f"{critique_redondance_inter_sections_feedback}\n"
                )
            critique_block += "Corrige explicitement tous ces points dans cette nouvelle version de la section."

        response_text = _generate_text_with_retry(
            contents=f"{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\nFICHE DE STRUCTURE DU CHAPITRE : {structure}\n\nCHAPITRE À RÉDIGER : Chapitre {chapitre}\n\nSECTION À RÉDIGER : Section {section}\n\nCONTRAINTE DE LONGUEUR : vise environ {target_words} mots, accepte uniquement une section entre {min_words} et {max_words} mots. Critiques à prendre en considération : {critique_block}\n\nVérification de cohérence avec la section précédente : {coherence_text}",
            context_label=f"section_ch{chapitre}_s{section}",
        )

        parsed = parse_section(response_text, chapitre, section)
        if not isinstance(parsed, dict):
            raise ValueError(
                f"Section parsee invalide pour ch{chapitre} s{section} (phase {phase_label}): objet JSON attendu."
            )
        if not isinstance(parsed.get("contenu"), str) or not parsed.get("contenu", "").strip():
            raise ValueError(
                f"Contenu de section vide apres parsing pour ch{chapitre} s{section} (phase {phase_label})."
            )

        # Nettoyage du contenu avant insertion dans le JSON de base.
        section_title = _find_section_title(chapitre, section)
        if section_title and isinstance(parsed.get("contenu"), str):
            cleaned_content, removed, matched_separator = strip_leading_title(
                parsed["contenu"], section_title
            )
            if removed:
                parsed["contenu"] = cleaned_content
                print(
                    f"Prefixe titre retire pour section_ch{chapitre}_s{section} ({matched_separator!r})."
                )

        _write_json(filepath, parsed, f"section ch{chapitre} s{section}")

        word_count = _count_content_words_from_file(filepath)
        print(
            f"Section {section} du chapitre {chapitre} sauvegardee -> {filename} ({word_count} mots)."
        )

        if min_words <= word_count <= max_words:
            if verification_section:
                verification_report = run_section_verification_report(chapitre, section)
                verification_ok = verification_report.get("decision") == "OUI"
                if not verification_ok:
                    critique_artefact_feedback = (
                        str(verification_report.get("critique_artefact") or "").strip()
                    )
                    critique_fluidite_feedback = (
                        str(verification_report.get("critique_fluidite") or "").strip()
                    )
                    critique_coherence_interne_feedback = (
                        str(verification_report.get("critique_coherence_interne") or "").strip()
                    )
                    critique_linguistique_feedback = (
                        str(verification_report.get("critique_linguistique") or "").strip()
                    )
                    critique_redondance_inter_sections_feedback = (
                        str(verification_report.get("critique_redondance_inter_sections") or "").strip()
                    )
                    if regen_attempt == max_attempts:
                        raise RuntimeError(
                            f"Section section_ch{chapitre}_s{section} invalidee par verification (reponse NON/indeterminee) apres {max_attempts} tentatives (phase {phase_label})."
                        )
                    print(
                        f"Section section_ch{chapitre}_s{section} invalidee par verification (reponse NON). "
                        f"Regeneration {phase_label} ({regen_attempt}/{max_attempts})..."
                    )
                    continue

                coherence_check(chapitre, section)
                print(
                    f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). "
                    "Verification section (OUI) puis coherence effectuees."
                )
            else:
                print(
                    f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). "
                    "verification_section desactivee: verification OUI/NON et coherence ignorees."
                )
            return

        if regen_attempt == max_attempts:
            raise RuntimeError(
                f"Section section_ch{chapitre}_s{section} hors plage ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}) apres {max_attempts} tentatives (phase {phase_label})."
            )

        length_issue = "trop courte" if word_count < min_words else "trop longue"
        print(
            f"Section section_ch{chapitre}_s{section} {length_issue} ({word_count} mots, attendu {min_words}-{max_words}, "
            f"cible {target_words}). Regeneration {phase_label} ({regen_attempt}/{max_attempts})..."
        )


def coherence_check(chapitre, section):
    chapitre = _to_int(chapitre, "chapitre")
    section = _to_int(section, "section")
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename
    fiche = _read_text(filepath, f"section ch{chapitre} s{section}")

    prompt_path = INPUT_DIR / "c_prompt.txt"
    prompt = _read_text(prompt_path, "prompt coherence")

    response_text = _generate_text_with_retry(
        contents=f"{prompt}\n\nSection à étudier :{fiche}",
        context_label=f"coherence_ch{chapitre}_s{section}",
    )
    parsed = parse_resume(response_text, chapitre, section)
    if not isinstance(parsed, dict):
        raise ValueError(f"Resume parse invalide pour ch{chapitre} s{section}: objet JSON attendu.")
    filename = f"coherence_ch{chapitre}_s{section}.json"
    filepath = RESUME_DIR / filename
    _write_json(filepath, parsed, f"coherence ch{chapitre} s{section}")
    return parsed


def merge_chapter_sections(chapitre_num: int):
    chapitre_num = _to_int(chapitre_num, "chapitre_num")
    chapitres = load_structure()
    chapitre_data = None
    for chap in chapitres:
        if not isinstance(chap, dict):
            continue
        try:
            chap_num = _to_int(chap.get("numero"), "chapitre.numero")
        except ValueError:
            continue
        if chap_num == chapitre_num:
            chapitre_data = chap
            break

    if chapitre_data is None:
        print(f"Chapitre {chapitre_num} introuvable dans structure_chapitre.json")
        return

    sections = []
    sections_data = chapitre_data.get("sections", [])
    if not isinstance(sections_data, list):
        raise ValueError(f"Sections invalides pour chapitre {chapitre_num}: liste attendue.")

    for sec in sections_data:
        if not isinstance(sec, dict):
            continue
        sec_num = _to_int(sec.get("numero"), f"section.numero (chapitre {chapitre_num})")
        filepath = SECTION_FR_DIR / f"section_ch{chapitre_num}_s{sec_num}.json"
        if not filepath.exists():
            print(f"   Fichier manquant : {filepath}")
            continue
        data = _read_json(filepath, f"section_fr ch{chapitre_num} s{sec_num}")
        if not isinstance(data, dict):
            raise ValueError(f"Format invalide pour section_fr ch{chapitre_num} s{sec_num}: objet JSON attendu.")
        sections.append({
            "section": sec_num,
            "titre": sec.get("titre_section", ""),
            "contenu": normalize_section_content(data.get("contenu", "")),
        })

    result = {
        "chapitre": chapitre_num,
        "titre": chapitre_data["titre"],
        "nb_sections": len(sections),
        "sections": sections,
    }

    output_path = CHAPITRE_DIR / f"chapitre_{chapitre_num}.json"
    _write_json(output_path, result, f"chapitre fusionne {chapitre_num}")

    print(f"Chapitre {chapitre_num} fusionné -> {output_path} ({len(sections)} sections)")


def merge_all_chapters():
    chapitres = load_structure()
    print(f"Fusion des sections pour {len(chapitres)} chapitres...\n")
    for chap in chapitres:
        if not isinstance(chap, dict):
            continue
        merge_chapter_sections(_to_int(chap.get("numero"), "chapitre.numero"))
    print("\nFusion terminée.")


if __name__ == '__main__':
    merge_all_chapters()
