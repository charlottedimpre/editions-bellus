import json
import os
from pathlib import Path

from llm_fallback import chat_with_major_error_fallback
from parser import parse_introduction, read_json_file as _read_json, read_text_file as _read_text

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")


def gen_intro():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    fiche_raw = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    _read_json(PLAN_DETAIL_PATH, "plan detaille")
    plan_raw = _read_text(PLAN_DETAIL_PATH, "plan detaille")

    prompt_path = INPUT_DIR / "i_prompt.txt"
    prompt = _read_text(prompt_path, "prompt introduction")

    response_content = chat_with_major_error_fallback(
        ollama_model=MODEL,
        message_content=f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
        context_label="introduction",
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )

    parsed = parse_introduction(response_content)
    if not isinstance(parsed, dict):
        raise ValueError("L'introduction parsee doit etre un objet JSON.")

    if not parsed.get("intro"):
        raise ValueError("Le contenu de l'introduction est vide apres parsing.")

    filepath = OUTPUT_DIR / "introduction.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    return parsed


if __name__ == '__main__':
    gen_intro()