import json
import os
from pathlib import Path

from ..models import Introduction, Conclusion, FilRouge, ChapitreDetails
from ..settings import BASE_DIR
from .config import *
from .fiche_cadrage import recup_fiche_cadrage
from .llm_fallback import chat_with_major_error_fallback
from .parser import parse_plan_detaille, clean_plan_detaille_titles_in_file, read_text_file
from .web_search.web_search import recup_web_search

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(BASE_DIR) / "Stage/input/"

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2


MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_fiche_cadrage_for_prompt(payload: dict) -> dict:
    """Exclut les champs bruts/legacy pour eviter les contradictions dans le prompt."""
    allowed_keys = [
        "sujet",
        "sommaire",
        "hors_perimetre",
        "contraintes_specifiques",
        "cible_principale",
        "cible",
        "niveau",
        "objectif_lecteur",
        "nbre_chapitres",
        "nb_chapitre",
    ]
    return {key: payload.get(key) for key in allowed_keys if key in payload}


def _normalize_ws_final(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"sources_web": payload}
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {"sources_web": []}
        try:
            parsed = json.loads(text)
            return _normalize_ws_final(parsed)
        except json.JSONDecodeError:
            return {"sources_web_raw": text}
    return {"sources_web_raw": str(payload)}


def sources(livre_id) -> dict:
    payload = recup_web_search(livre_id)
    return _normalize_ws_final(payload)


def _chat_with_retry(message_content: str, context_label: str) -> str:
    return chat_with_major_error_fallback(
        ollama_model=MODEL_COURT,
        message_content=message_content,
        context_label=context_label,
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def plan_detail(livre_id):
    prompt_path = INPUT_DIR / "pd_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt plan detaille", require_non_empty=False)

    # Fiche de cadrage
    fiche_cadrage_raw = recup_fiche_cadrage(livre_id)
    fiche_cadrage_payload = json.loads(fiche_cadrage_raw)

    expected_chapters = None
    fiche_list = fiche_cadrage_payload.get("fiche_cadrage", [])
    if fiche_list and isinstance(fiche_list, list):
        fiche_data = fiche_list[0]
        raw_expected = fiche_data.get("nbre_chapitres") or fiche_data.get("nb_chapitre")
        if raw_expected is not None:
            expected_chapters = int(raw_expected)
        fiche_cadrage_for_prompt = _build_fiche_cadrage_for_prompt(fiche_data)
    else:
        fiche_cadrage_for_prompt = {"raw_fiche": fiche_cadrage_payload}

    fiche_cadrage_str = json.dumps(fiche_cadrage_for_prompt, ensure_ascii=False, indent=2)
    sources_web = json.dumps(sources(livre_id), ensure_ascii=False, indent=2)

    message = (
        f"{prompt}\n\n"
        f"FICHE DE CADRAGE (JSON) : {fiche_cadrage_str}\n\n"
        f"SOURCES WEB (JSON) : {sources_web}"
    )

    response_content = _chat_with_retry(message, context_label="plan_detaille")
    parsed = parse_plan_detaille(response_content)

    if not isinstance(parsed, dict):
        raise ValueError("Le plan detaille parse doit etre un objet JSON.")

    chapitres = parsed.get("chapitres")
    if not isinstance(chapitres, list) or len(chapitres) == 0:
        raise ValueError("Le plan detaille parse doit contenir une liste de chapitres non vide.")

    # Vérification du nombre de chapitres, avec relance si incorrect
    if expected_chapters is not None and len(chapitres) != expected_chapters:
        print(
            f"[WARN] Nombre de chapitres invalide ({len(chapitres)} au lieu de {expected_chapters}). "
            "Nouvelle tentative de generation forcee."
        )
        response_content = _chat_with_retry(
            message_content=(
                f"{message}\n\n"
                f"CONTRAINTE ABSOLUE: genere EXACTEMENT {expected_chapters} chapitres. "
                "Ne renvoie que le format demande."
            ),
            context_label="plan_detaille_count_fix",
        )
        parsed = parse_plan_detaille(response_content)
        chapitres = parsed.get("chapitres")
        if not isinstance(chapitres, list) or len(chapitres) != expected_chapters:
            raise ValueError(
                f"Nombre de chapitres invalide: attendu {expected_chapters}, "
                f"obtenu {len(chapitres) if isinstance(chapitres, list) else 'invalide'} apres correction."
            )

    ajout_plan_detail_bdd(parsed, livre_id)
    return recup_plan_detail(livre_id)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_plan_detail_bdd(data: dict, livre_id: int):
    intro_data = data.get("introduction", {})
    Introduction.objects.create(
        contexte=intro_data.get("contexte"),
        importance=intro_data.get("importance"),
        adresse_a=intro_data.get("adresse_a"),
        organisation=intro_data.get("organisation"),
        promesse=intro_data.get("promesse"),
        livre_id=livre_id,
    )

    conclusion_data = data.get("conclusion", {})
    Conclusion.objects.create(
        synthese=conclusion_data.get("synthese"),
        logique_ensemble=conclusion_data.get("logique_ensemble"),
        prochaines_etapes=conclusion_data.get("prochaines_etapes"),
        livre_id=livre_id,
    )

    fil_rouge_data = data.get("exemple_fil_rouge", {})
    FilRouge.objects.create(
        personnage=fil_rouge_data.get("personnage"),
        situation_depart=fil_rouge_data.get("situation_depart"),
        evolution=fil_rouge_data.get("evolution"),
        livre_id=livre_id,
    )

    for chapitre_data in data.get("chapitres", []):
        ChapitreDetails.objects.create(
            numero=chapitre_data.get("numero"),
            titre=chapitre_data.get("titre"),
            traite=chapitre_data.get("traite"),
            ne_traite_pas=chapitre_data.get("ne_traite_pas"),
            pourquoi_distinct=chapitre_data.get("pourquoi_distinct"),
            livre_id=livre_id,
        )

    print("Donnees inserees avec succes.")


def recup_plan_detail(livre_id: int) -> str:
    intro = Introduction.objects.filter(livre_id=livre_id).last()
    conclusion = Conclusion.objects.filter(livre_id=livre_id).last()
    fil_rouge = FilRouge.objects.filter(livre_id=livre_id).last()
    chapitres = ChapitreDetails.objects.filter(livre_id=livre_id).all().order_by("numero")

    return json.dumps(
        {
            "introduction": {
                "contexte": intro.contexte if intro else None,
                "importance": intro.importance if intro else None,
                "adresse_a": intro.adresse_a if intro else None,
                "organisation": intro.organisation if intro else None,
                "promesse": intro.promesse if intro else None,
            },
            "chapitres": [
                {
                    "numero": chap.numero,
                    "titre": chap.titre,
                    "traite": chap.traite,
                    "ne_traite_pas": chap.ne_traite_pas,
                    "pourquoi_distinct": chap.pourquoi_distinct,
                }
                for chap in chapitres
            ],
            "conclusion": {
                "synthese": conclusion.synthese if conclusion else None,
                "logique_ensemble": conclusion.logique_ensemble if conclusion else None,
                "prochaines_etapes": conclusion.prochaines_etapes if conclusion else None,
            },
            "exemple_fil_rouge": {
                "personnage": fil_rouge.personnage if fil_rouge else None,
                "situation_depart": fil_rouge.situation_depart if fil_rouge else None,
                "evolution": fil_rouge.evolution if fil_rouge else None,
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def reset_plan_detail(livre_id: int):
    Introduction.objects.filter(livre_id=livre_id).delete()
    Conclusion.objects.filter(livre_id=livre_id).delete()
    FilRouge.objects.filter(livre_id=livre_id).delete()
    ChapitreDetails.objects.filter(livre_id=livre_id).delete()