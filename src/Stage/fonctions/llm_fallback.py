import os
import time
from pathlib import Path

from dotenv import load_dotenv
from ollama import chat

try:
    from google import genai
    from google.genai.errors import ServerError
except ImportError:  # pragma: no cover - dependance optionnelle a l'execution
    genai = None
    ServerError = Exception


ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_FALLBACK_MODELS = os.getenv("GEMINI_FALLBACK_MODELS", "")
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY_SECONDS = 5
OLLAMA_FALLBACK_MODELS = os.getenv("ED_BELLUS_OLLAMA_FALLBACK_MODELS", "")


def _get_gemini_candidate_models() -> list[str]:
    candidates: list[str] = []

    if GEMINI_MODEL and GEMINI_MODEL.strip():
        candidates.append(GEMINI_MODEL.strip())

    if GEMINI_FALLBACK_MODELS.strip():
        candidates.extend([m.strip() for m in GEMINI_FALLBACK_MODELS.split(",") if m.strip()])

    # Defaults robustes si aucun modele explicite n'est fourni.
    candidates.extend([
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    ])

    unique_candidates: list[str] = []
    for model in candidates:
        if model not in unique_candidates:
            unique_candidates.append(model)

    return unique_candidates


def _get_ollama_candidate_models(primary_model: str | None) -> list[str]:
    candidates: list[str] = []

    if primary_model and primary_model.strip():
        candidates.append(primary_model.strip())

    if OLLAMA_FALLBACK_MODELS.strip():
        candidates.extend([m.strip() for m in OLLAMA_FALLBACK_MODELS.split(",") if m.strip()])

    unique_candidates: list[str] = []
    for model in candidates:
        if model not in unique_candidates:
            unique_candidates.append(model)

    return unique_candidates


def _is_retryable_gemini_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    err_text = str(exc).lower()
    return any(token in err_text for token in [
        "status code: 500",
        "status code: 502",
        "status code: 503",
        "status code: 504",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
    ])


def _is_model_not_found_gemini_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True

    err_text = str(exc).lower()
    return any(token in err_text for token in [
        "404",
        "not found",
        "model not found",
        "unknown model",
        "unsupported model",
    ])


def _is_retryable_ollama_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    err_text = str(exc).lower()
    return any(token in err_text for token in ["status code: 500", "status code: 503", "internal server error", "timeout"])


def _is_major_ollama_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and 400 <= status_code < 500 and status_code != 429:
        return True

    err_text = str(exc).lower()
    major_tokens = [
        "requires a subscription",
        "upgrade for access",
        "insufficient_quota",
        "status code: 401",
        "status code: 403",
        "status code: 404",
    ]
    return any(token in err_text for token in major_tokens)


def _chat_with_gemini(message_content: str, context_label: str, trigger_error: Exception | None = None) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError(
            f"Fallback Gemini impossible ({context_label}): GEMINI_API_KEY manquante."
            f" Erreur initiale: {trigger_error}"
        )

    if genai is None:
        raise RuntimeError(
            f"Fallback Gemini impossible ({context_label}): package google-genai indisponible."
            f" Erreur initiale: {trigger_error}"
        )

    client = genai.Client(api_key=gemini_api_key)
    models = _get_gemini_candidate_models()
    if not models:
        raise RuntimeError(
            f"Fallback Gemini impossible ({context_label}): aucun modele Gemini disponible."
            f" Erreur initiale: {trigger_error}"
        )

    last_error: Exception | None = None

    for model in models:
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=message_content,
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError(f"Reponse vide de Gemini ({context_label}).")
                print(f"[INFO] Fallback Gemini actif pour {context_label} (modele: {model}).")
                return text
            except Exception as err:
                last_error = err

                if _is_model_not_found_gemini_error(err):
                    print(f"[WARN] Modele Gemini invalide/introuvable pour {context_label}: {model} ({err})")
                    break

                if not _is_retryable_gemini_error(err) or attempt == GEMINI_MAX_RETRIES:
                    break

                print(
                    f"[WARN] Gemini indisponible pour {context_label} "
                    f"(modele {model}, tentative {attempt}/{GEMINI_MAX_RETRIES}) : {err}"
                )
                time.sleep(GEMINI_RETRY_DELAY_SECONDS)

        if len(models) > 1:
            print(f"[WARN] Echec avec le modele Gemini {model}. Tentative du modele suivant...")

    raise RuntimeError(
        f"Echec fallback Gemini ({context_label}) apres essais de {len(models)} modele(s): {last_error}"
    )


def chat_with_major_error_fallback(
    *,
    ollama_model: str | None,
    message_content: str,
    context_label: str,
    ollama_max_retries: int = 3,
    ollama_retry_delay_seconds: int = 2,
) -> str:
    models = _get_ollama_candidate_models(ollama_model)
    if not models:
        print(f"[WARN] Aucun modele Ollama configure, fallback Gemini direct pour {context_label}.")
        return _chat_with_gemini(message_content=message_content, context_label=context_label)

    last_error: Exception | None = None

    for model in models:
        for attempt in range(1, ollama_max_retries + 1):
            try:
                response = chat(model=model, messages=[{"role": "user", "content": message_content}])
                if response.message is None or not response.message.content:
                    raise RuntimeError(f"Reponse vide du modele ({context_label}).")
                return response.message.content.strip()
            except Exception as exc:
                last_error = exc

                if _is_major_ollama_error(exc):
                    print(f"[WARN] Erreur majeure Ollama detectee ({context_label}, modele {model}), bascule modele suivant: {exc}")
                    break

                if not _is_retryable_ollama_error(exc):
                    print(f"[WARN] Erreur Ollama non recuperable ({context_label}, modele {model}), tentative modele suivant: {exc}")
                    break

                if attempt < ollama_max_retries:
                    print(
                        f"[WARN] Ollama indisponible pour {context_label} "
                        f"(modele {model}, tentative {attempt}/{ollama_max_retries}) : {exc}"
                    )
                    time.sleep(ollama_retry_delay_seconds)

        if len(models) > 1:
            print(f"[WARN] Echec avec le modele {model}. Tentative du modele suivant...")

    print(f"[WARN] Ollama en echec apres {ollama_max_retries} tentatives ({context_label}), bascule Gemini.")
    return _chat_with_gemini(message_content=message_content, context_label=context_label, trigger_error=last_error)
