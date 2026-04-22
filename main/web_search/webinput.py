from pathlib import Path
import json
import os
import time

from ollama import chat
from ollama import ChatResponse
from parser import read_json_file as _read_json, read_text_file as _read_text

MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")
LLM_MAX_RETRIES = 4
LLM_BASE_DELAY_SECONDS = 2

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _is_retryable_ollama_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    err_text = str(exc).lower()
    return any(token in err_text for token in [
        "status code: 500",
        "status code: 503",
        "internal server error",
        "timeout",
        "temporarily unavailable",
    ])


def _chat_with_retry(message_content: str, context_label: str) -> str:
    last_error: Exception | None = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response: ChatResponse = chat(model=MODEL_COURT, messages=[
                {
                    "role": "user",
                    "content": message_content,
                }
            ])

            if response.message is None or not response.message.content:
                raise RuntimeError(f"Reponse vide du modele ({context_label}).")

            return response.message.content
        except Exception as exc:
            last_error = exc
            if not _is_retryable_ollama_error(exc) or attempt == LLM_MAX_RETRIES:
                break

            delay = LLM_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(
                f"[WARN] LLM indisponible pour {context_label} "
                f"(tentative {attempt}/{LLM_MAX_RETRIES}) : {exc}. "
                f"Nouvelle tentative dans {delay}s."
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Echec appel LLM pour {context_label} avec le modele {MODEL_COURT} "
        f"apres {LLM_MAX_RETRIES} tentatives: {last_error}"
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