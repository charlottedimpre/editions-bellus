import json
import os
from pathlib import Path
from typing import Any

from ..models import FicheCadrage
from ..settings import BASE_DIR
from .config import *
from .llm_fallback import chat_with_major_error_fallback
from .parser import parse_fiche_cadrage, read_text_file

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_DIR = Path(BASE_DIR) / "Stage/input/fiche_cadrage/"

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")

LEVEL_FILES = {
    "1": "fc_debutant",
    "2": "fc_intermediaire",
    "3": "fc_avance",
}

NIVEAU_TEXTS = {
    "fc_debutant": (
        "Débutant (suppose aucune connaissance préalable sur le sujet, n'exige aucun vocabulaire "
        "technique acquis, nécessite des définitions explicites des concepts dès leur première "
        "apparition, privilégie une progression lente et cumulative, impose des transitions "
        "pédagogiques entre chaque chapitre, exclut les raccourcis implicites de raisonnement, "
        "demande des formulations concrètes et accessibles sans simplification trompeuse, anticipe "
        "les confusions fréquentes d'un grand public novice, intègre un rappel régulier des limites "
        "et des conditions d'application, et vise une autonomie de compréhension de base sans "
        "prérequis de lecture complémentaire)"
    ),
    "fc_intermediaire": (
        "Intermédiaire (suppose des bases acquises et un vocabulaire courant du sujet, autorise des "
        "références techniques sans redéfinition exhaustive, vise une progression structurée avec "
        "des sauts raisonnables, met l'accent sur la consolidation et l'application, explicite les "
        "nuances et cas limites, tolère des synthèses plus denses, et propose des approfondissements "
        "optionnels sans exiger de prérequis avancés)"
    ),
    "fc_avance": (
        "Avancé (suppose une maîtrise solide des fondamentaux et du vocabulaire spécialisé, accepte "
        "des raisonnements compacts, privilégie la profondeur, les arbitrages et les controverses, "
        "met en avant les limites méthodologiques, les hypothèses et les exceptions, et vise un "
        "lecteur capable de relier le contenu à des cadres théoriques ou pratiques avancés)"
    ),
}

PROMPT_FILE = "fc_prompt.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_sujet(sujet: Any) -> str:
    if not isinstance(sujet, str):
        raise TypeError("Le sujet doit etre une chaine de caracteres.")
    cleaned = sujet.strip()
    if not cleaned:
        raise ValueError("Le sujet ne peut pas etre vide.")
    return cleaned


def _apply_prompt_variables(prompt: str, niveau: str) -> str:
    """Remplace {{NIVEAU}} dans le prompt par le texte descriptif correspondant."""
    if "{{NIVEAU}}" not in prompt:
        return prompt
    niveau_text = NIVEAU_TEXTS.get(niveau)
    if not niveau_text:
        raise ValueError(f"Niveau inconnu pour {{NIVEAU}}: {niveau!r}")
    return prompt.replace("{{NIVEAU}}", niveau_text)


def _ensure_nb_chapitre(parsed: dict) -> dict:
    """Garantit que la clé nb_chapitre est présente et valide dans le résultat parsé."""
    fiche = parsed.get("fiche_cadrage", [{}])[0] if "fiche_cadrage" in parsed else parsed

    nb = fiche.get("nbre_chapitres") or fiche.get("nb_chapitre")

    if nb is None:
        raise ValueError(
            "La réponse du LLM ne contient pas la balise <nb_chapitre> (ni nbre_chapitres). "
            "Vérifiez le prompt fc_prompt.txt pour vous assurer que cette balise est bien demandée."
        )

    try:
        nb = int(nb)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"La valeur de nb_chapitre n'est pas un entier valide : {nb!r}"
        ) from exc

    if nb <= 0:
        raise ValueError(f"nb_chapitre doit être un entier positif, reçu : {nb}")

    # Normalise sous la clé nb_chapitre dans tous les cas
    fiche["nb_chapitre"] = nb
    fiche.pop("nbre_chapitres", None)

    if "fiche_cadrage" in parsed:
        parsed["fiche_cadrage"][0] = fiche
    else:
        parsed = fiche

    return parsed


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def fiche_cadrage(sujet: str, niveau: str) -> dict:
    sujet = _normalize_sujet(sujet)

    if not isinstance(niveau, str) or not niveau.strip():
        raise ValueError("Le niveau de prompt doit etre une chaine non vide.")

    prompt_path = INPUT_DIR / PROMPT_FILE
    prompt = read_text_file(prompt_path, f"prompt {PROMPT_FILE}", require_non_empty=False)
    prompt = _apply_prompt_variables(prompt, niveau)

    response_content = chat_with_major_error_fallback(
        ollama_model=MODEL_COURT,
        message_content=f"{prompt}\n\nSUJET : {sujet}",
        context_label="fiche_cadrage",
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )

    parsed = parse_fiche_cadrage(response_content)
    if not isinstance(parsed, dict):
        raise ValueError("La fiche de cadrage parsee doit etre un objet JSON.")

    parsed = _ensure_nb_chapitre(parsed)

    return parsed


def fc(sujet: str, niveau: str, livre_id: int):
    niveau_file = LEVEL_FILES[niveau]
    txt = fiche_cadrage(sujet, niveau_file)
    print(txt)
    ajout_bdd_fiche_cadrage(txt, livre_id, parse=True)
    insert_fc(livre_id)
    print(recup_fiche_cadrage(livre_id))
    return recup_fiche_cadrage(livre_id)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_bdd_fiche_cadrage(fiche_cadr, livre_id: int, parse: bool = False):
    if isinstance(fiche_cadr, str):
        fiche_cadr = json.loads(fiche_cadr)

    if not parse:
        fiche_cadr = parse_fiche_cadrage(fiche_cadr)

    if "fiche_cadrage" in fiche_cadr:
        fiche_cadr = fiche_cadr["fiche_cadrage"][0]

    FicheCadrage.objects.create(
        livre_id=livre_id,
        sujet=fiche_cadr["sujet"],
        nb_chapitre=fiche_cadr["nb_chapitre"],
        hors_perimetre=fiche_cadr["hors_perimetre"],
        contraintes_specifiques=fiche_cadr.get("contraintes_specifiques"),
        cible=fiche_cadr.get("cible_principale") or fiche_cadr.get("cible"),
        niveau=fiche_cadr["niveau"],
        objectif_lecteur=fiche_cadr["objectif_lecteur"],
    )


def recup_fiche_cadrage(livre_id: int) -> str:
    fiche = FicheCadrage.objects.filter(livre_id=livre_id).first()

    if not fiche:
        return json.dumps({"fiche_cadrage": []}, ensure_ascii=False, indent=2)

    return json.dumps(
        {
            "fiche_cadrage": [
                {
                    "sujet": fiche.sujet,
                    "nb_chapitre": fiche.nb_chapitre,
                    "hors_perimetre": fiche.hors_perimetre,
                    "contraintes_specifiques": fiche.contraintes_specifiques,
                    "cible": fiche.cible,
                    "niveau": fiche.niveau,
                    "objectif_lecteur": fiche.objectif_lecteur,
                }
            ]
        },
        ensure_ascii=False,
        indent=2,
    )


def reset_fiche_cadrage(livre_id):
    FicheCadrage.objects.filter(livre_id=livre_id).delete()


def insert_fc(livre_id: int) -> bool:
    fiche_payload = json.loads(recup_fiche_cadrage(livre_id))

    if not isinstance(fiche_payload, dict):
        raise ValueError("La fiche cadrage doit etre un objet JSON.")

    fiche_list = fiche_payload.get("fiche_cadrage", [])
    if not fiche_list:
        print("Aucune fiche en base.")
        return False

    fiche_data = fiche_list[0]

    try:
        expected_chapters = int(recup_nb_chapitres())
    except (TypeError, ValueError) as exc:
        raise ValueError("nb_chapitres doit etre un entier.") from exc

    current_chapters = fiche_data.get("nb_chapitre")

    if current_chapters != expected_chapters:
        fiche_data["nb_chapitre"] = expected_chapters
        reset_fiche_cadrage()
        ajout_bdd_fiche_cadrage(fiche_data, livre_id, parse=True)
        print(f"Mise a jour de nb_chapitre: {current_chapters} -> {expected_chapters}")
        return True

    print(f"Aucune mise a jour: nb_chapitre est deja a {expected_chapters}.")
    return False