import json
import os
import re
import time
from pathlib import Path

from ...models import Preface
from ...settings import BASE_DIR
from ..config import *
from ..fiche_cadrage import recup_fiche_cadrage
from ..llm_fallback import chat_with_major_error_fallback
from ..parser import parse_preface, read_text_file
from ..plan_detaille import recup_plan_detail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(BASE_DIR) / "Stage/input/prepostface/"

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL_LONG = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")

MIN_WORDS = 200
MAX_WORDS = 260

PROMPT_FILE = "pr_prompt.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_words(text: str) -> int:
    """Compte le nombre de mots dans un texte."""
    return len(re.findall(r"\b\w+\b", text, re.UNICODE))


def _extract_contenu(parsed: dict) -> str:
    """Extrait le contenu textuel depuis le dict parsé (clé preface ou intro)."""
    contenu = parsed.get("preface") or parsed.get("intro")
    if not contenu:
        raise ValueError("Le contenu de la préface est vide après parsing.")
    return contenu


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def gen_preface(livre_id: int) -> dict:
    """
    Génère la préface via le LLM avec contrôle du nombre de mots,
    puis persiste le résultat en base.

    Args:
        livre_id: Identifiant du livre cible.

    Returns:
        Le dict parsé de la préface générée.
    """
    fiche_raw = recup_fiche_cadrage(livre_id)
    plan_raw = recup_plan_detail(livre_id)

    prompt_path = INPUT_DIR / PROMPT_FILE
    prompt = read_text_file(prompt_path, f"prompt {PROMPT_FILE}", require_non_empty=False)

    parsed = None
    max_attempts = 5

    for attempt in range(1, max_attempts + 1):
        print(f"Tentative {attempt}/{max_attempts} pour générer la préface...")

        message = f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}"

        response_content = chat_with_major_error_fallback(
            ollama_model=MODEL_LONG,
            message_content=message,
            context_label="preface" if attempt == 1 else "preface_retry",
            ollama_max_retries=LLM_MAX_RETRIES,
            ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
        )

        parsed = parse_preface(response_content)
        if not isinstance(parsed, dict):
            raise ValueError("La préface parsée doit être un objet JSON.")

        contenu = _extract_contenu(parsed)
        word_count = count_words(contenu)
        print(f"Nombre de mots : {word_count} (cible : {MIN_WORDS}-{MAX_WORDS})")

        if MIN_WORDS <= word_count <= MAX_WORDS:
            print(f"✓ Préface validée avec {word_count} mots")
            break

        if attempt < max_attempts:
            if word_count < MIN_WORDS:
                adjustment_msg = (
                    f"La préface est trop courte ({word_count} mots). "
                    f"Elle doit contenir entre {MIN_WORDS} et {MAX_WORDS} mots. Rallonge-la."
                )
            else:
                adjustment_msg = (
                    f"La préface est trop longue ({word_count} mots). "
                    f"Elle doit contenir entre {MIN_WORDS} et {MAX_WORDS} mots. Raccourcis-la."
                )
            prompt = (
                f"{prompt}\n\n[AJUSTEMENT REQUIS : {adjustment_msg}]"
            )
            time.sleep(1)
        else:
            print(f"⚠ Nombre maximum de tentatives atteint. Validation avec {word_count} mots.")

    ajout_bdd_preface(parsed, livre_id)
    print(recup_preface(livre_id))
    return recup_preface_dict(livre_id)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_bdd_preface(parsed: dict, livre_id: int) -> None:
    """Insère ou met à jour la préface en base pour le livre donné."""
    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    contenu = _extract_contenu(parsed)
    nb_mots = count_words(contenu)

    Preface.objects.update_or_create(
        livre_id=livre_id,
        defaults={
            "contenu": contenu,
            "nb_mots": nb_mots,
        },
    )


def recup_preface(livre_id: int) -> str:
    """Retourne la préface sérialisée en JSON, ou un objet vide."""
    preface = Preface.objects.filter(livre_id=livre_id).first()

    if not preface:
        return json.dumps({"preface": []}, ensure_ascii=False, indent=2)

    return json.dumps(
        {
            "preface": [
                {
                    "contenu": preface.contenu,
                    "nb_mots": preface.nb_mots,
                }
            ]
        },
        ensure_ascii=False,
        indent=2,
    )


def recup_preface_dict(livre_id: int) -> dict:
    """Retourne la préface sous forme de dict Python."""
    return json.loads(recup_preface(livre_id))


def reset_preface(livre_id: int) -> None:
    Preface.objects.filter(livre_id=livre_id).delete()