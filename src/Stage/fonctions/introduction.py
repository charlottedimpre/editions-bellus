import json
from pathlib import Path

from ollama import ChatResponse, chat

from .parser import parse_introduction
import os
from ..settings import BASE_DIR
from .fiche_cadrage import recup_fiche_cadrage
from .plan_detaille import recup_plan_detail
from ..models import IntroductionTexte

from .llm_fallback import chat_with_major_error_fallback

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")

def gen_intro():
    fiche_raw = recup_fiche_cadrage()

    plan_raw = recup_plan_detail()

    prompt = os.path.join(BASE_DIR, 'Stage/input/i_prompt.txt')
    file = open(prompt, 'r')
    prompt = file.read()

    response_content = chat_with_major_error_fallback(
        ollama_model=MODEL,
        message_content=f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
        context_label="introduction",
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )
    parsed = parse_introduction(response_content)

    ajout_intro_bdd(parsed)


if __name__ == '__main__':
    gen_intro()

def ajout_intro_bdd(data):
    IntroductionTexte.objects.create(
        intro=data['intro'],
    )

def recup_intro():
    intro = IntroductionTexte.objects.last()

    return json.dumps({
        "intro": intro.intro if intro else None
    }, ensure_ascii=False, indent=2)

def reset_intro():
    IntroductionTexte.objects.all().delete()