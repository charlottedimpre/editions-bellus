import json
import os
from pathlib import Path

from ..models import ConclusionTexte, FicheSection
from ..settings import BASE_DIR
from .fiche_cadrage import recup_fiche_cadrage
from .llm_fallback import chat_with_major_error_fallback
from .parser import parse_conclusion, read_text_file
from .plan_detaille import recup_plan_detail
from .structure_chapitre import recup_chapitres_sections

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(BASE_DIR) / "Stage/input/"

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_structure(livre_id: int) -> list[dict]:
    data = json.loads(recup_chapitres_sections(livre_id))
    if not isinstance(data, list):
        raise ValueError("La structure des chapitres doit etre une liste.")
    return data


def build_resume_mashup(chapitres: list[dict], livre_id: int) -> list[dict]:
    """Construit le mashup des résumés de cohérence depuis la BDD (FicheSection)."""
    mashup = []

    for chapitre in chapitres:
        if not isinstance(chapitre, dict):
            continue

        ch_num = int(chapitre.get("numero", 0))
        sections = chapitre.get("sections", [])
        if not isinstance(sections, list):
            raise ValueError(f"chapitre.sections invalide pour chapitre {ch_num}")

        for section in sections:
            if not isinstance(section, dict):
                continue

            sec_num = int(section.get("numero", 0))

            try:
                fiche = FicheSection.objects.get(
                    chapitre_numero=ch_num,
                    section_numero=sec_num,
                    livre_id=livre_id,
                )
                coherence = {
                    "chapitre": fiche.chapitre_numero,
                    "section": fiche.section_numero,
                    "these_centrale": fiche.these_centrale,
                    "arguments_cles": fiche.arguments_cles,
                    "concepts_introduits": fiche.concepts_introduits,
                    "a_ne_pas_repeter": fiche.a_ne_pas_repeter,
                    "liens_chapitres": fiche.liens_chapitres,
                    "ton_angle": fiche.ton_angle,
                }
                mashup.append({
                    "chapitre": ch_num,
                    "section": sec_num,
                    "resume": coherence,
                })
            except FicheSection.DoesNotExist:
                mashup.append({
                    "chapitre": ch_num,
                    "section": sec_num,
                    "resume": None,
                    "missing": True,
                })

    mashup.sort(key=lambda x: (x["chapitre"], x["section"]))
    return mashup


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def gen_conclu(livre_id: int):
    chapitres = load_structure(livre_id)

    fiche_raw = recup_fiche_cadrage(livre_id)
    plan_raw = recup_plan_detail(livre_id)
    resume_mashup = build_resume_mashup(chapitres, livre_id)

    prompt_path = INPUT_DIR / "c_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt conclusion", require_non_empty=False)

    response_content = chat_with_major_error_fallback(
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

    parsed = parse_conclusion(response_content)
    if not isinstance(parsed, dict):
        raise ValueError("La conclusion parsee doit etre un objet JSON.")

    if not parsed.get("conclusion"):
        raise ValueError("Le contenu de la conclusion est vide apres parsing.")

    ajout_conclusion_bdd(parsed, livre_id)
    return recup_conclusion(livre_id)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_conclusion_bdd(data: dict, livre_id: int):
    ConclusionTexte.objects.create(
        conclusion=data["conclusion"],
        livre_id=livre_id,
    )


def recup_conclusion(livre_id: int) -> str:
    conclu = ConclusionTexte.objects.filter(livre_id=livre_id).last()
    return json.dumps(
        {"conclusion": conclu.conclusion if conclu else None},
        ensure_ascii=False,
        indent=2,
    )


def reset_conclusion(livre_id: int):
    ConclusionTexte.objects.filter(livre_id=livre_id).delete()