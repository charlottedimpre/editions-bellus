from pathlib import Path
from ..settings import BASE_DIR
from ollama import chat
from ollama import ChatResponse
from .parser import parse_fiche_cadrage, to_json_file, read_text_file
import json
import os
from ..models import FicheCadrage
from typing import Any
import time
from .config import *

INPUT_DIR = os.path.join(BASE_DIR, 'Stage/input/fiche_cadrage/')

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")

LEVEL_FILES = {
    "1": "fc_debutant",
    "2": "fc_intermediaire",
    "3": "fc_avance",
}

def _read_text(path: Path, label: str) -> str:
    return read_text_file(path, label, require_non_empty=False)


def _normalize_sujet(sujet: Any) -> str:
    if not isinstance(sujet, str):
        raise TypeError("Le sujet doit etre une chaine de caracteres.")
    cleaned = sujet.strip()
    if not cleaned:
        raise ValueError("Le sujet ne peut pas etre vide.")
    return cleaned


def _is_retryable_ollama_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    err_text = str(exc).lower()
    return any(token in err_text for token in ["status code: 500", "status code: 503", "internal server error", "timeout"])


def _chat_with_retry(model: str, message_content: str, context_label: str) -> str:
    last_error: Exception | None = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = chat(model=model, messages=[
                {
                    "role": "user",
                    "content": message_content,
                },
            ])
            if response.message is None or not response.message.content:
                raise RuntimeError(f"Reponse vide du modele ({context_label}).")
            return response.message.content
        except Exception as exc:
            last_error = exc
            if not _is_retryable_ollama_error(exc) or attempt == LLM_MAX_RETRIES:
                break
            print(
                f"[WARN] Ollama indisponible pour {context_label} "
                f"(tentative {attempt}/{LLM_MAX_RETRIES}) : {exc}"
            )
            time.sleep(LLM_RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Echec appel LLM ({context_label}) apres {LLM_MAX_RETRIES} tentatives: {last_error}")

def _build_output_payload(parsed_data, titre_saisi: str) -> dict:
    if isinstance(parsed_data, dict):
        payload = dict(parsed_data)
    else:
        payload = {"donnees_parsees": parsed_data}

    payload["titre_saisi_utilisateur"] = titre_saisi

    if not payload.get("sujet"):
        payload["sujet"] = titre_saisi

    return payload

def fiche_cadrage(sujet: str, niveau: str):
    prompt = os.path.join(INPUT_DIR, f"{niveau}.txt")
    file = open(prompt, 'r', encoding="utf-8")
    prompt = file.read()


    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nSUJET : {sujet}',
        },
    ])
    parsed = parse_fiche_cadrage(response.message.content)
    return parsed

def fc(sujet, niveau):
    niveau_file = LEVEL_FILES[niveau]
    txt = fiche_cadrage(sujet, niveau_file)
    ajout_bdd_fiche_cadrage(txt, True)
    insert_fc()
    return recup_fiche_cadrage()


def insert_fc():
    fiche_payload = json.loads(recup_fiche_cadrage())

    if not isinstance(fiche_payload, dict):
        raise ValueError("La fiche cadrage doit être un objet JSON.")

    fiche_list = fiche_payload.get("fiche_cadrage", [])

    if not fiche_list:
        print("Aucune fiche en base")
        return False

    fiche_data = fiche_list[0]  # ✅ IMPORTANT

    try:
        expected_chapters = int(recup_nb_chapitres())
    except (TypeError, ValueError) as exc:
        raise ValueError("nb_chapitres doit être un entier.") from exc

    fiche_key = "nb_chapitre" if "nb_chapitre" in fiche_data else "nb_chapitre"
    current_chapters = fiche_data.get(fiche_key)

    if current_chapters != expected_chapters:
        fiche_data[fiche_key] = expected_chapters

        # 🔥 reset + insert propre
        reset_fiche_cadrage()
        ajout_bdd_fiche_cadrage(fiche_data, True)

        print(f"Mise a jour de {fiche_key}: {current_chapters} -> {expected_chapters}")
        return True

    print(f"Aucune mise a jour: {fiche_key} est deja a {expected_chapters}.")
    return False

def ajout_bdd_fiche_cadrage(fiche_cadr, parse : bool = False):
    if isinstance(fiche_cadr, str):
        fiche_cadr = json.loads(fiche_cadr)

    if not parse:
        fiche_cadr = parse_fiche_cadrage(fiche_cadr)

    if "fiche_cadrage" in fiche_cadr:
        fiche_cadr = fiche_cadr["fiche_cadrage"][0]
    FicheCadrage.objects.create(
        sujet=fiche_cadr['sujet'],
        sommaire=fiche_cadr['sommaire'],
        hors_perimetre=fiche_cadr['hors_perimetre'],
        cible=fiche_cadr.get('cible_principale') or fiche_cadr.get('cible'),
        niveau=fiche_cadr['niveau'],
        objectif_lecteur=fiche_cadr['objectif_lecteur'],
        nb_chapitre=fiche_cadr.get('nbre_chapitres') or fiche_cadr.get('nb_chapitre'),
    )

def recup_fiche_cadrage():
    fiche = FicheCadrage.objects.last()

    if not fiche:
        return json.dumps({
            "fiche_cadrage": []
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        "fiche_cadrage": [{
            "sujet": fiche.sujet,
            "sommaire": fiche.sommaire,
            "hors_perimetre": fiche.hors_perimetre,
            "cible": fiche.cible,
            "niveau": fiche.niveau,
            "objectif_lecteur": fiche.objectif_lecteur,
            "nb_chapitre": fiche.nb_chapitre
        }]
    }, ensure_ascii=False, indent=2)

def reset_fiche_cadrage():
    FicheCadrage.objects.all().delete()