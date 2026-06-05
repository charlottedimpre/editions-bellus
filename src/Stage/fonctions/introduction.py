import json
import os
from pathlib import Path

from ..models import IntroductionTexte
from ..settings import BASE_DIR
from .fiche_cadrage import recup_fiche_cadrage
from .llm_fallback import chat_with_major_error_fallback
from .parser import parse_introduction, read_text_file
from .plan_detaille import recup_plan_detail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(BASE_DIR) / "Stage/input/"

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def gen_intro(livre_id: int):
    fiche_raw = recup_fiche_cadrage(livre_id)
    plan_raw = recup_plan_detail(livre_id)

    prompt_path = INPUT_DIR / "i_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt introduction", require_non_empty=False)

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

    ajout_intro_bdd(parsed, livre_id)
    return recup_intro(livre_id)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_intro_bdd(data: dict, livre_id: int):
    IntroductionTexte.objects.create(
        intro=data["intro"],
        livre_id=livre_id,
    )


def recup_intro(livre_id: int) -> str:
    intro = IntroductionTexte.objects.filter(livre_id=livre_id).last()

    return json.dumps(
        {"intro": intro.intro if intro else None},
        ensure_ascii=False,
        indent=2,
    )


def reset_intro(livre_id: int):
    IntroductionTexte.objects.filter(livre_id=livre_id).delete()