import json
from pathlib import Path

from ollama import ChatResponse, chat

from parser import parse_structure_chapitres, read_json_file as _read_json, read_text_file as _read_text

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def structure_chapitre():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    fiche_raw = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    _read_json(PLAN_DETAIL_PATH, "plan detaille")
    plan_raw = _read_text(PLAN_DETAIL_PATH, "plan detaille")

    prompt_path = INPUT_DIR / "sc_prompt.txt"
    prompt = _read_text(prompt_path, "prompt structure chapitre")

    response: ChatResponse = chat(model="mistral-large-3:675b-cloud", messages=[
        {
            "role": "user",
            "content": f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
        },
    ])

    if response.message is None or not response.message.content:
        raise ValueError("Reponse vide du modele pour la structure de chapitre.")

    parsed = parse_structure_chapitres(response.message.content)
    if not isinstance(parsed, list):
        raise ValueError("La structure de chapitre parsee doit etre une liste.")

    if not parsed:
        raise ValueError("La structure de chapitre parsee est vide.")

    filepath = OUTPUT_DIR / "structure_chapitre.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    return parsed


if __name__ == '__main__':
    structure_chapitre()