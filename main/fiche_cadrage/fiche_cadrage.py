from pathlib import Path
import os
import time
from typing import Any

from ollama import chat
from parser import parse_fiche_cadrage, read_json_file, read_text_file, to_json_file

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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


def fiche_cadrage(sujet: str, niveau: str):
    sujet = _normalize_sujet(sujet)
    if not isinstance(niveau, str) or not niveau.strip():
        raise ValueError("Le niveau de prompt doit etre une chaine non vide.")

    input_path = INPUT_DIR / f"{niveau}.txt"

    prompt = _read_text(input_path, f"prompt {niveau}")

    response_content = _chat_with_retry(
        model=MODEL_COURT,
        message_content=f"{prompt}\n\nSUJET : {sujet}",
        context_label="fiche_cadrage",
    )

    parsed = parse_fiche_cadrage(response_content)
    if not isinstance(parsed, dict):
        raise ValueError("La fiche de cadrage parsee doit etre un objet JSON.")

    return parsed


def _build_output_payload(parsed_data, titre_saisi: str) -> dict:
    if isinstance(parsed_data, dict):
        payload = dict(parsed_data)
    else:
        payload = {"donnees_parsees": parsed_data}

    payload["titre_saisi_utilisateur"] = titre_saisi

    if not payload.get("sujet"):
        payload["sujet"] = titre_saisi

    return payload


def fc():
    sujet = input("Quel est le titre de votre livre ? ")
    while len(sujet.strip()) < 1:
        print("Le titre ne peut pas être vide.")
        sujet = input("Quel est le titre de votre livre ? ")

    sujet = sujet.strip()

    niveau_input = input("Quel niveau souhaitez-vous ? (1 - Débutant, 2 - Intermédiaire, 3 - Avancé) : ")

    while niveau_input not in ['1', '2', '3']:
        print("Le niveau doit être 1, 2 ou 3.")
        niveau_input = input("Quel niveau souhaitez-vous ? (1 - Débutant, 2 - Intermédiaire, 3 - Avancé) : ")

    niveau_file = LEVEL_FILES[niveau_input]
    txt = fiche_cadrage(sujet, niveau_file)
    output_payload = _build_output_payload(txt, sujet)
    print(f"Fiche de cadrage générée : {sujet} {niveau_file}")
    to_json_file(output_payload, OUTPUT_DIR / "fiche_cadrage.json")


def insert_fc():
    fiche_path = OUTPUT_DIR / "fiche_cadrage.json"
    config_path = BASE_DIR.parent / "config.json"

    fiche_payload = read_json_file(fiche_path, "fiche cadrage", require_non_empty=True)
    config_payload = read_json_file(config_path, "config", require_non_empty=True)

    if not isinstance(fiche_payload, dict):
        raise ValueError("Le fichier fiche_cadrage.json doit contenir un objet JSON.")
    if not isinstance(config_payload, dict):
        raise ValueError("Le fichier config.json doit contenir un objet JSON.")

    livre_config = config_payload.get("livre")
    if not isinstance(livre_config, dict) or "nbre_chapitres" not in livre_config:
        raise ValueError("Le champ livre.nbre_chapitres est manquant dans config.json.")

    try:
        expected_chapters = int(livre_config["nbre_chapitres"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Le champ livre.nbre_chapitres de config.json doit etre un entier.") from exc

    fiche_key = "nbre_chapitres" if "nbre_chapitres" in fiche_payload else "nb_chapitres"
    current_chapters = fiche_payload.get(fiche_key)

    if current_chapters != expected_chapters:
        fiche_payload[fiche_key] = expected_chapters
        to_json_file(fiche_payload, fiche_path)
        print(f"Mise a jour de {fiche_key}: {current_chapters} -> {expected_chapters}")
        return True

    print(f"Aucune mise a jour: {fiche_key} est deja a {expected_chapters}.")
    return False


if __name__ == '__main__':
    fc()
