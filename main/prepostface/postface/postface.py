import json
import os
import re
import time
from pathlib import Path

from llm_fallback import chat_with_major_error_fallback
from parser import parse_postface, read_json_file as _read_json, read_text_file as _read_text

BASE_DIR = Path(__file__).resolve().parent
BASE_DIR_PATH = BASE_DIR.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR_PATH.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR_PATH.parent / "plan_detaille" / "output" / "plan_detaille.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")
MIN_WORDS = 200
MAX_WORDS = 260


def count_words(text):
    """Compte le nombre de mots dans un texte."""
    words = re.findall(r'\b\w+\b', text, re.UNICODE)
    return len(words)


def gen_postface():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    fiche_raw = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    _read_json(PLAN_DETAIL_PATH, "plan detaille")
    plan_raw = _read_text(PLAN_DETAIL_PATH, "plan detaille")

    prompt_path = INPUT_DIR / "po_prompt.txt"
    prompt = _read_text(prompt_path, "prompt postface")

    parsed = None
    attempt = 0
    max_attempts = 5

    while attempt < max_attempts:
        attempt += 1
        print(f"Tentative {attempt}/{max_attempts} pour générer la postface...")

        response_content = chat_with_major_error_fallback(
            ollama_model=MODEL,
            message_content=f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
            context_label="postface",
            ollama_max_retries=LLM_MAX_RETRIES,
            ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
        )

        parsed = parse_postface(response_content)
        if not isinstance(parsed, dict):
            raise ValueError("la postface parsee doit etre un objet JSON.")

        if not (parsed.get("postface") or parsed.get("intro")):
            raise ValueError("Le contenu de la postface est vide apres parsing.")

        # Récupérer le contenu de la postface
        postface_content = parsed.get("postface") or parsed.get("intro")
        word_count = count_words(postface_content)

        print(f"Nombre de mots : {word_count} (cible : {MIN_WORDS}-{MAX_WORDS})")

        if MIN_WORDS <= word_count <= MAX_WORDS:
            print(f"✓ Postface validée avec {word_count} mots")
            break
        else:
            if attempt < max_attempts:
                if word_count < MIN_WORDS:
                    adjustment_msg = f"La postface est trop courte ({word_count} mots). Elle doit contenir entre {MIN_WORDS} et {MAX_WORDS} mots. Rallonge-la."
                else:
                    adjustment_msg = f"La postface est trop longue ({word_count} mots). Elle doit contenir entre {MIN_WORDS} et {MAX_WORDS} mots. Raccourcis-la."

                prompt_with_adjustment = f"{prompt}\n\n[AJUSTEMENT REQUISE : {adjustment_msg}]\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}"
                response_content = chat_with_major_error_fallback(
                    ollama_model=MODEL,
                    message_content=prompt_with_adjustment,
                    context_label="postface_retry",
                    ollama_max_retries=LLM_MAX_RETRIES,
                    ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
                )
                parsed = parse_postface(response_content)
                time.sleep(1)
            else:
                print(f"⚠ Nombre maximum de tentatives atteint. Validation avec {word_count} mots.")
                break

    filepath = OUTPUT_DIR / "postface.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    return parsed


if __name__ == '__main__':
    gen_postface()
