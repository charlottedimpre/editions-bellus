import json
import sys
from pathlib import Path
import os
from ollama import ChatResponse, chat
from .llm_fallback import chat_with_major_error_fallback

from Stage.fonctions.fiche_cadrage import recup_fiche_cadrage
from Stage.fonctions.plan_detaille import recup_plan_detail
from Stage.models import ConclusionTexte
from ..settings import BASE_DIR
from .structure_chapitre import recup_chapitres_sections



ROOT_DIR = BASE_DIR.parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from .parser import parse_conclusion, parse_resume


LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")

def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    return recup_chapitres_sections()


def build_resume_mashup(chapitres: list[dict]) -> list[dict]:
    resume_dir = BASE_DIR.parent / "section" / "output" / "resume"
    mashup = []

    for chapitre in chapitres:
        ch_num = int(chapitre["numero"])
        for section in chapitre["sections"]:
            sec_num = int(section["numero"])
            coherence_path = resume_dir / f"coherence_ch{ch_num}_s{sec_num}.json"

            if not coherence_path.exists():
                mashup.append({
                    "chapitre": ch_num,
                    "section": sec_num,
                    "resume": None,
                    "missing_file": str(coherence_path),
                })
                continue

            with coherence_path.open("r", encoding="utf-8") as f:
                coherence = json.load(f)

            if isinstance(coherence, str):
                coherence = parse_resume(coherence, ch_num, sec_num)

            mashup.append({
                "chapitre": ch_num,
                "section": sec_num,
                "resume": coherence,
            })

    mashup.sort(key=lambda x: (x["chapitre"], x["section"]))
    return mashup


def gen_conclu():
    chapitres = load_structure()
    chapitres = json.loads(chapitres)

    fiche_raw = recup_fiche_cadrage()

    plan_raw = recup_plan_detail()

    resume_mashup = build_resume_mashup(chapitres)

    prompt = os.path.join(BASE_DIR, 'Stage/input/c_prompt.txt')
    file = open(prompt, 'r')
    prompt = file.read()

    response = chat_with_major_error_fallback(
        ollama_model=MODEL,
        message_content=(
            f"{prompt}\n\n"
            f"FICHE DE CADRAGE :{fiche_raw}\n\n"
            f"PLAN DETAILE :{plan_raw}\n\n"
            f"RESUMES MASHUP (JSON) :{json.dumps(resume_mashup, ensure_ascii=False)}"
        ),
        context_label="conclusion",
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )
    parsed = parse_conclusion(response)
    ajout_conclusion_bdd(parsed)


if __name__ == '__main__':
    gen_conclu()

def ajout_conclusion_bdd(data):
    ConclusionTexte.objects.create(
        conclusion=data['conclusion'],
    )

def recup_conclusion():
    conclu = ConclusionTexte.objects.last()

    return json.dumps({
        "conclusion": conclu.conclusion if conclu else None
    }, ensure_ascii=False, indent=2)

def reset_conclusion():
    ConclusionTexte.objects.all().delete()