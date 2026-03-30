import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from parser import parse_section, parse_resume
from section.section_cleaner import normalize_section_content, strip_leading_title

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


def gen_section(chapitre, section):
    with FICHE_PATH.open("r", encoding="utf-8") as f:
        fiche = f.read()

    with PLAN_PATH.open("r", encoding="utf-8") as f:
        plan = f.read()

    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        structure = f.read()

    prompt_path = INPUT_DIR / "s_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    coherence = ""
    if chapitre == 1 and section == 1:
        coherence = "il n'y a pas de section précédente, c'est la première section du premier chapitre, aucune vérification de cohérence nécessaire."
        print(f"{coherence}")
    elif section == 1:
        chapitres = load_structure()
        nb_sec = None
        for chap in chapitres:
            if int(chap["numero"]) == chapitre - 1:
                nb_sec = len(chap["sections"])
                break

        if nb_sec is not None:
            coherence_path = RESUME_DIR / f"coherence_ch{chapitre - 1}_s{nb_sec}.json"
            with coherence_path.open("r", encoding="utf-8") as f:
                coherence = f.read()
            print(f"Vérification de cohérence avec la section précédente : coherence_ch{chapitre - 1}_s{nb_sec}.json...")
        else:
            coherence = "Section précédente introuvable dans la structure."
            print(coherence)
    else:
        coherence_path = RESUME_DIR / f"coherence_ch{chapitre}_s{section - 1}.json"
        with coherence_path.open("r", encoding="utf-8") as f:
            coherence = f.read()
        print(f"Vérification de cohérence avec la section précédente : coherence_ch{chapitre}_s{section - 1}.json...")

    coherence_text = coherence if coherence else ""

    response_text = _generate_text_with_retry(
        contents=f"{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\nFICHE DE STRUCTURE DU CHAPITRE : {structure}\n\nCHAPITRE À RÉDIGER : Chapitre {chapitre}\n\nSECTION À RÉDIGER : Section {section}\n\n\nVérification de cohérence avec la section précédente : {coherence_text}",
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

    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"Section {section} du chapitre {chapitre} sauvegardée -> {filename}")

    coherence_check(chapitre, section)

    print("Vérification de cohérence effectuée pour la section précédente.")


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
