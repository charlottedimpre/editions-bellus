import json
from pathlib import Path

from ollama import ChatResponse, chat

from parser import parse_introduction

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def gen_intro():
    with FICHE_CADRAGE_PATH.open("r", encoding="utf-8") as f:
        fiche_raw = f.read()

    with PLAN_DETAIL_PATH.open("r", encoding="utf-8") as f:
        plan_raw = f.read()

    prompt_path = INPUT_DIR / "i_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DÉTAILLÉ :{plan_raw}',
        },
    ])
    parsed = parse_introduction(response.message.content)

    filepath = OUTPUT_DIR / "introduction.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    gen_intro()