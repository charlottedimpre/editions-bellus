import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from parser import parse_section, parse_resume
from section.section_cleaner import normalize_section_content, strip_leading_title
from section.section_verification import verification_section_report as run_section_verification_report

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
MAX_SECTION_REGEN_ATTEMPTS = 3
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
                f"Gemini indisponible (503) [{context_label}] tentative {attempt}/{MAX_RETRIES}, nouvelle tentative dans {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_section_title(chapitre: int, section: int) -> str | None:
    for chap in load_structure():
        if int(chap.get("numero", 0)) != chapitre:
            continue
        for sec in chap.get("sections", []):
            if int(sec.get("numero", 0)) == section:
                title = sec.get("titre_section")
                if isinstance(title, str) and title.strip():
                    return title.strip()
    return None


def _count_words(text: str) -> int:
    # Compte les mots en preservant les apostrophes/tirets dans les tokens.
    return len(re.findall(r"[\wÀ-ÖØ-öø-ÿ]+(?:['’-][\wÀ-ÖØ-öø-ÿ]+)*", text, flags=re.UNICODE))


def _count_content_words_from_file(filepath: Path) -> int:
    with filepath.open("r", encoding="utf-8") as f:
        section_data = json.load(f)
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


def _load_previous_coherence_context(chapitre: int, section: int, structure_data: list[dict]) -> str:
    if chapitre == 1 and section == 1:
        msg = "il n'y a pas de section précédente, c'est la première section du premier chapitre, aucune vérification de cohérence nécessaire."
        print(msg)
        return msg

    coherence_path = None
    coherence_name = ""

    if section == 1:
        nb_sec = None
        for chap in structure_data:
            if int(chap["numero"]) == chapitre - 1:
                nb_sec = len(chap["sections"])
                break
        if nb_sec is None:
            msg = "Section précédente introuvable dans la structure."
            print(msg)
            return msg

        coherence_name = f"coherence_ch{chapitre - 1}_s{nb_sec}.json"
        coherence_path = RESUME_DIR / coherence_name
    else:
        coherence_name = f"coherence_ch{chapitre}_s{section - 1}.json"
        coherence_path = RESUME_DIR / coherence_name

    if coherence_path.exists():
        with coherence_path.open("r", encoding="utf-8") as f:
            coherence = f.read()
        print(f"Vérification de cohérence avec la section précédente : {coherence_name}...")
        return coherence

    print(
        f"[WARN] Fichier de cohérence manquant: {coherence_name}. "
        "Continuation sans contexte de cohérence précédent."
    )
    return "Contexte de cohérence précédent indisponible (resume manquant)."


def gen_section(chapitre, section, verification_section: bool = True):
    with FICHE_PATH.open("r", encoding="utf-8") as f:
        fiche = f.read()

    with PLAN_PATH.open("r", encoding="utf-8") as f:
        plan = f.read()

    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        structure = f.read()

    prompt_path = INPUT_DIR / "s_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    structure_data = load_structure()
    total_sections = _count_total_sections(structure_data)
    min_words, max_words, target_words = _compute_section_word_bounds(total_sections)
    print(
        f"Contraintes dynamiques section: cible {target_words} mots, plage {min_words}-{max_words} (total sections: {total_sections}, max livre: {MAX_BOOK_WORDS})."
    )

    coherence = _load_previous_coherence_context(chapitre, section, structure_data)

    coherence_text = coherence if coherence else ""
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename
    critique_artefact_feedback = ""
    critique_fluidite_feedback = ""
    critique_coherence_interne_feedback = ""
    critique_linguistique_feedback = ""
    critique_redondance_inter_sections_feedback = ""

    for regen_attempt in range(1, MAX_SECTION_REGEN_ATTEMPTS + 1):
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

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)

        word_count = _count_content_words_from_file(filepath)
        print(
            f"Section {section} du chapitre {chapitre} sauvegardée -> {filename} ({word_count} mots)."
        )

        if min_words <= word_count <= max_words:
            if verification_section:
                verification_report = run_section_verification_report(chapitre, section)
                verification_ok = verification_report.get("decision") == "OUI"
                print(verification_report)
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
                    if regen_attempt == MAX_SECTION_REGEN_ATTEMPTS:
                        raise RuntimeError(
                            f"Section section_ch{chapitre}_s{section} invalidee par verification (reponse NON/indeterminee) apres {MAX_SECTION_REGEN_ATTEMPTS} tentatives."
                        )
                    if critique_artefact_feedback:
                        print(
                            f"Critique artefact injectee pour regeneration: {critique_artefact_feedback}"
                        )
                    if critique_fluidite_feedback:
                        print(
                            f"Critique fluidite injectee pour regeneration: {critique_fluidite_feedback}"
                        )
                    if critique_coherence_interne_feedback:
                        print(
                            f"Critique coherence interne injectee pour regeneration: {critique_coherence_interne_feedback}"
                        )
                    if critique_linguistique_feedback:
                        print(
                            f"Critique linguistique injectee pour regeneration: {critique_linguistique_feedback}"
                        )
                    if critique_redondance_inter_sections_feedback:
                        print(
                            "Critique redondance inter-sections injectee pour regeneration: "
                            f"{critique_redondance_inter_sections_feedback}"
                        )
                    print(
                        f"Section section_ch{chapitre}_s{section} invalidee par verification (reponse NON). Regeneration ({regen_attempt}/{MAX_SECTION_REGEN_ATTEMPTS})..."
                    )
                    continue

                coherence_check(chapitre, section)
                print(
                    f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). Verification section (OUI) puis coherence effectuees."
                )
            else:
                print(
                    f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). verification_section desactivee: verification OUI/NON et coherence ignorees."
                )
            return

        if regen_attempt == MAX_SECTION_REGEN_ATTEMPTS:
            raise RuntimeError(
                f"Section section_ch{chapitre}_s{section} hors plage ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}) apres {MAX_SECTION_REGEN_ATTEMPTS} tentatives."
            )

        length_issue = "trop courte" if word_count < min_words else "trop longue"
        print(
            f"Section section_ch{chapitre}_s{section} {length_issue} ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). Regeneration ({regen_attempt}/{MAX_SECTION_REGEN_ATTEMPTS})..."
        )


def coherence_check(chapitre, section):
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename
    with filepath.open("r", encoding="utf-8") as f:
        fiche = f.read()

    prompt_path = INPUT_DIR / "c_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    response_text = _generate_text_with_retry(
        contents=f"{prompt}\n\nSection à étudier :{fiche}",
        context_label=f"coherence_ch{chapitre}_s{section}",
    )
    parsed = parse_resume(response_text, chapitre, section)
    filename = f"coherence_ch{chapitre}_s{section}.json"
    filepath = RESUME_DIR / filename
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    return parsed


def merge_chapter_sections(chapitre_num: int):
    chapitres = load_structure()
    chapitre_data = None
    for chap in chapitres:
        if int(chap["numero"]) == chapitre_num:
            chapitre_data = chap
            break

    if chapitre_data is None:
        print(f"Chapitre {chapitre_num} introuvable dans structure_chapitre.json")
        return

    sections = []
    for sec in chapitre_data["sections"]:
        sec_num = int(sec["numero"])
        filepath = SECTION_FR_DIR / f"section_ch{chapitre_num}_s{sec_num}.json"
        if not filepath.exists():
            print(f"   Fichier manquant : {filepath}")
            continue
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)
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
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Chapitre {chapitre_num} fusionné -> {output_path} ({len(sections)} sections)")


def merge_all_chapters():
    chapitres = load_structure()
    print(f"Fusion des sections pour {len(chapitres)} chapitres...\n")
    for chap in chapitres:
        merge_chapter_sections(int(chap["numero"]))
    print("\nFusion terminée.")


if __name__ == '__main__':
    merge_all_chapters()
