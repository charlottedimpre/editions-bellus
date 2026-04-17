import json
import os
import time
from pathlib import Path

from ollama import ChatResponse, chat

from parser import parse_structure_chapitres, read_json_file as _read_json, read_text_file as _read_text

MODEL = "mistral-large-3:675b-cloud"
LLM_MAX_RETRIES = 4
LLM_BASE_DELAY_SECONDS = 2

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _get_candidate_models() -> list[str]:
    # Optional override/fallback list, comma-separated.
    # Example: ED_BELLUS_STRUCTURE_MODELS="mistral-large-3:675b-cloud,kimi-k2.5:cloud"
    raw = os.getenv("ED_BELLUS_STRUCTURE_MODELS", "").strip()
    if not raw:
        return [MODEL]

    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or [MODEL]


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
    models = _get_candidate_models()

    for model in models:
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                response: ChatResponse = chat(model=model, messages=[
                    {
                        "role": "user",
                        "content": message_content,
                    },
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
                    f"(modele {model}, tentative {attempt}/{LLM_MAX_RETRIES}) : {exc}. "
                    f"Nouvelle tentative dans {delay}s."
                )
                time.sleep(delay)

        if len(models) > 1:
            print(f"[WARN] Echec avec le modele {model}. Tentative du modele suivant...")

    raise RuntimeError(
        f"Echec appel LLM pour {context_label} "
        f"apres {LLM_MAX_RETRIES} tentatives par modele "
        f"(modeles testes: {', '.join(models)}): {last_error}"
    )


def structure_chapitre():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    fiche_raw = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    _read_json(PLAN_DETAIL_PATH, "plan detaille")
    plan_raw = _read_text(PLAN_DETAIL_PATH, "plan detaille")

    prompt_path = INPUT_DIR / "sc_prompt.txt"
    prompt = _read_text(prompt_path, "prompt structure chapitre")

    raw_response = _chat_with_retry(
        message_content=f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
        context_label="structure_chapitre",
    )

    parsed = parse_structure_chapitres(raw_response)
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