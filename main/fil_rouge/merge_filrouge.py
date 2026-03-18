import json
from pathlib import Path

from ollama import chat, ChatResponse

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SECTION_DIR = BASE_DIR.parent / "section" / "output" / "section_fr"
SECTION_OUTPUT_DIR = BASE_DIR.parent / "section" / "output" / "section"
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
FIL_ROUGE_PATH = OUTPUT_DIR / "fil_rouge.json"


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_insertion(fil_rouge_data: dict, chapitre: int, section: int) -> str:
    for ins in fil_rouge_data.get("insertions", []):
        if int(ins.get("chapitre", -1)) == int(chapitre) and int(ins.get("section", -1)) == int(section):
            return ins.get("contenu", "")
    return ""


def incorporer(chapitre, section):
    prompt_path = INPUT_DIR / "mf_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_OUTPUT_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_data = json.load(f)

    with FIL_ROUGE_PATH.open("r", encoding="utf-8") as f:
        fil_rouge_data = json.load(f)

    exemple = get_insertion(fil_rouge_data, chapitre, section)

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': (
                f"{prompt}\n\n"
                f"SECTION : {section_data.get('contenu', '')}\n\n"
                f"FIL ROUGE : {exemple}\n\n"
                f"NUMERO CHAPITRE : {chapitre}\n\n"
                f"NUMERO SECTION : {section}"
            ),
        },
    ])

    section_data["contenu"] = response.message.content
    return section_data


def merge_filrouge_wrapper():
    chapitres = load_structure()
    for chapitre in chapitres:
        chapitre_num = int(chapitre["numero"])
        for section in chapitre.get("sections", []):
            section_num = int(section["numero"])
            result = incorporer(chapitre_num, section_num)
            print(f"Résultat pour Chapitre {chapitre_num} Section {section_num}\n{'-' * 80}")

            filepath = SECTION_DIR / f"section_ch{chapitre_num}_s{section_num}.json"
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    merge_filrouge_wrapper()