from pathlib import Path
import json
import os

from llm_fallback import chat_with_major_error_fallback
from parser import read_json_file as _read_json, read_text_file as _read_text

MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")
LLM_MAX_RETRIES = 4
LLM_BASE_DELAY_SECONDS = 2

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _chat_with_retry(message_content: str, context_label: str) -> str:
    return chat_with_major_error_fallback(
        ollama_model=MODEL_COURT,
        message_content=message_content,
        context_label=context_label,
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_BASE_DELAY_SECONDS,
    )


def webinputresponse():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    sujet = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    input_path = INPUT_DIR / "ws_search.txt"
    prompt_input = _read_text(input_path, "prompt web search")

    return _chat_with_retry(
        message_content=f"{prompt_input}\n\nSUJET : {sujet}",
        context_label="webinput",
    )


def webinput_wrapper():
    raw_response = webinputresponse()
    try:
        response_obj = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        preview = raw_response[:300].replace("\n", " ")
        raise ValueError(
            f"La reponse webinput doit etre un JSON valide. Extrait: {preview!r}"
        ) from exc

    if not isinstance(response_obj, dict):
        raise ValueError("Le JSON webinput doit etre un objet.")

    filepath = OUTPUT_DIR / "ws_search.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(response_obj, f, ensure_ascii=False, indent=2)

    print("Web search response generated")


if __name__ == '__main__':
    webinput_wrapper()