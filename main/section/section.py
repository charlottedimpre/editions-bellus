import json
from pathlib import Path

from ollama import ChatResponse, chat

from parser import parse_section, parse_resume

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SECTION_DIR = OUTPUT_DIR / "section"
SECTION_FR_DIR = OUTPUT_DIR / "section_fr"
RESUME_DIR = OUTPUT_DIR / "resume"
CHAPITRE_DIR = OUTPUT_DIR / "chapitre"
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
FICHE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"

SECTION_DIR.mkdir(parents=True, exist_ok=True)
RESUME_DIR.mkdir(parents=True, exist_ok=True)
CHAPITRE_DIR.mkdir(parents=True, exist_ok=True)


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_section_content(raw_content):
    if isinstance(raw_content, dict):
        return (
            raw_content.get("section_mise_a_jour")
            or raw_content.get("contenu")
            or raw_content.get("texte")
            or ""
        )

    if isinstance(raw_content, str):
        candidate = raw_content.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                decoded = json.loads(candidate)
                if isinstance(decoded, dict):
                    return (
                        decoded.get("section_mise_a_jour")
                        or decoded.get("contenu")
                        or decoded.get("texte")
                        or raw_content
                    )
            except json.JSONDecodeError:
                return raw_content
    return raw_content


def coherence_check(chapitre, section):
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename
    with filepath.open("r", encoding="utf-8") as f:
        fiche = f.read()

    prompt_path = INPUT_DIR / "c_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nSection à étudier :{fiche}',
        },
    ])
    parsed = parse_resume(response.message.content, chapitre, section)
    filename = f"coherence_ch{chapitre}_s{section}.json"
    filepath = RESUME_DIR / filename
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    return parsed


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

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\nFICHE DE STRUCTURE DU CHAPITRE : {structure}\n\nCHAPITRE À RÉDIGER : Chapitre {chapitre}\n\nSECTION À RÉDIGER : Section {section}\n\n\nVérification de cohérence avec la section précédente : {coherence_text}',
        },
    ])

    parsed = parse_section(response.message.content, chapitre, section)
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = SECTION_DIR / filename
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"Section {section} du chapitre {chapitre} sauvegardée -> {filename}")

    coherence_check(chapitre, section)

    print("Vérification de cohérence effectuée pour la section précédente.")


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
            "contenu": _normalize_section_content(data.get("contenu", "")),
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
