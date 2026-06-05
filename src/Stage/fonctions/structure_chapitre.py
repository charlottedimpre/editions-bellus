import json
import os
from pathlib import Path

from ..models import ChapitreDetails, SectionDetaillee
from ..settings import BASE_DIR
from .config import *
from .fiche_cadrage import recup_fiche_cadrage
from .llm_fallback import chat_with_major_error_fallback
from .parser import parse_structure_chapitres, read_text_file
from .plan_detaille import recup_plan_detail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(BASE_DIR) / "Stage/input/"

MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT") or "mistral-large-3:675b-cloud"
LLM_MAX_RETRIES = 4
LLM_BASE_DELAY_SECONDS = 2

WORD_TARGET_CONFIG = {
    "total_mots_cibles_livre": 15000,
    "fourchette_mots_ratio": 0.40,
}


# ---------------------------------------------------------------------------
# Word target helpers
# ---------------------------------------------------------------------------

def _resolve_word_target_config(mode: str | None) -> dict:
    config = dict(WORD_TARGET_CONFIG)
    if str(mode) != "1":
        return config

    raw_total = recup_nb_mots_cibles()
    if raw_total is None:
        raise ValueError("Mode 1 actif: 'livre.nbre_mots_cible' est requis dans config.")

    config["total_mots_cibles_livre"] = int(raw_total)

    raw_fourchette = recup_fourchette_mots_ratio()
    if raw_fourchette is not False:
        config["fourchette_mots_ratio"] = float(raw_fourchette)

    return config


def _get_total_mots_cibles_livre(word_target_config: dict) -> int:
    total = int(word_target_config.get("total_mots_cibles_livre", 0))
    if total <= 0:
        raise ValueError("La configuration total_mots_cibles_livre doit etre un entier positif.")
    return total


def _add_word_count_per_section(chapitres: list[dict], word_target_config: dict) -> list[dict]:
    total_mots_livre = _get_total_mots_cibles_livre(word_target_config)
    total_mots_structure = max(1, total_mots_livre)

    all_sections: list[dict] = []
    for chapitre in chapitres:
        sections = chapitre.get("sections")
        if not isinstance(sections, list) or not sections:
            continue
        for section in sections:
            if isinstance(section, dict):
                all_sections.append(section)

    total_sections = len(all_sections)
    if total_sections <= 0:
        raise ValueError("Impossible de repartir les mots: aucune section valide detectee.")

    base = total_mots_structure // total_sections
    reste = total_mots_structure % total_sections
    fourchette_ratio = max(0.0, float(word_target_config.get("fourchette_mots_ratio", 0.40)))
    demi_fourchette = fourchette_ratio / 2

    for idx, section in enumerate(all_sections):
        mots_section = base + (1 if idx < reste else 0)
        mots_section = max(1, mots_section)

        min_mots = max(1, round(mots_section * (1 - demi_fourchette)))
        max_mots = max(min_mots, round(mots_section * (1 + demi_fourchette)))

        section["nombre_mots_section"] = mots_section
        section["mots_cible"] = f"{min_mots}-{max_mots}"

    for chapitre in chapitres:
        sections = chapitre.get("sections")
        if not isinstance(sections, list):
            chapitre["total_mots_chapitre"] = 0
            continue

        total_chapitre = 0
        for section in sections:
            if not isinstance(section, dict):
                continue
            total_chapitre += int(section.get("nombre_mots_section", 0) or 0)

        chapitre["total_mots_chapitre"] = total_chapitre

    return chapitres


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def _get_candidate_models() -> list[str]:
    raw = os.getenv("ED_BELLUS_STRUCTURE_MODELS", "").strip()
    if not raw:
        return [MODEL]
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or [MODEL]


def _chat_with_retry(message_content: str, context_label: str) -> str:
    last_error: Exception | None = None
    models = _get_candidate_models()

    for model in models:
        try:
            return chat_with_major_error_fallback(
                ollama_model=model,
                message_content=message_content,
                context_label=context_label,
                ollama_max_retries=LLM_MAX_RETRIES,
                ollama_retry_delay_seconds=LLM_BASE_DELAY_SECONDS,
            )
        except Exception as exc:
            last_error = exc
            if len(models) > 1:
                print(f"[WARN] Echec avec le modele {model}. Tentative du modele suivant...")

    raise RuntimeError(
        f"Echec appel LLM pour {context_label} avec les modeles {', '.join(models)}: {last_error}"
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def structure_chapitre(livre_id: int, mode: str = "0"):
    word_target_config = _resolve_word_target_config(mode)

    fiche_raw = recup_fiche_cadrage(livre_id)
    plan_raw = recup_plan_detail(livre_id)

    prompt_path = INPUT_DIR / "sc_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt structure chapitre", require_non_empty=False)

    raw_response = _chat_with_retry(
        message_content=f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
        context_label="structure_chapitre",
    )

    parsed = parse_structure_chapitres(raw_response)

    if not isinstance(parsed, list):
        raise ValueError("La structure de chapitre parsee doit etre une liste.")

    if not parsed:
        raise ValueError("La structure de chapitre parsee est vide.")

    parsed = _add_word_count_per_section(parsed, word_target_config)

    ajout_structure_chapitre_bdd(parsed, livre_id)
    return recup_chapitres_sections(livre_id)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_structure_chapitre_bdd(data: list, livre_id: int):
    for chapitre_data in data:
        numero_chapitre = chapitre_data.get("numero")

        chapitre = ChapitreDetails.objects.filter(
            numero=int(numero_chapitre),
            livre_id=livre_id,
        ).first()

        if not chapitre:
            print(f"Chapitre {numero_chapitre} introuvable, skip.")
            continue

        for section_data in chapitre_data.get("sections", []):
            SectionDetaillee.objects.create(
                chapitre=chapitre,
                numero=int(section_data.get("numero")) if section_data.get("numero") else None,
                titre_section=section_data.get("titre_section"),
                objectif=section_data.get("objectif"),
                concept_cle=section_data.get("concept_cle"),
                exemple=section_data.get("exemple"),
                limite=section_data.get("limite"),
                mots_cible=section_data.get("mots_cible"),
                livre_id=livre_id,
            )

    print("Sections ajoutees avec succes.")


def recup_chapitres_sections(livre_id: int) -> str:
    chapitres = ChapitreDetails.objects.filter(livre_id=livre_id).order_by("numero")

    result = []
    for chapitre in chapitres:
        chapitre_dict = {
            "numero": str(chapitre.numero),
            "titre": chapitre.titre,
            "total_mots_chapitre": None,
            "sections": [],
        }

        for section in chapitre.sections.all().order_by("numero"):
            chapitre_dict["sections"].append({
                "numero": str(section.numero),
                "titre_section": section.titre_section,
                "objectif": section.objectif,
                "concept_cle": section.concept_cle,
                "exemple": section.exemple,
                "limite": section.limite,
                "mots_cible": section.mots_cible,
            })

        result.append(chapitre_dict)

    return json.dumps(result, ensure_ascii=False, indent=2)


def reset_structure(livre_id: int):
    SectionDetaillee.objects.filter(livre_id=livre_id).delete()