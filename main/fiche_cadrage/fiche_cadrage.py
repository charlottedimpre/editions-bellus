from pathlib import Path
import os
from typing import Any

from llm_fallback import chat_with_major_error_fallback
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


def _read_text(path: Path, label: str) -> str:
    return read_text_file(path, label, require_non_empty=False)


def _normalize_sujet(sujet: Any) -> str:
    if not isinstance(sujet, str):
        raise TypeError("Le sujet doit etre une chaine de caracteres.")
    cleaned = sujet.strip()
    if not cleaned:
        raise ValueError("Le sujet ne peut pas etre vide.")
    return cleaned


def _apply_prompt_variables(prompt: str, niveau: str) -> str:
    if "{{NIVEAU}}" not in prompt:
        return prompt
    niveau_text = NIVEAU_TEXTS.get(niveau)
    if not niveau_text:
        raise ValueError(f"Niveau inconnu pour {{NIVEAU}}: {niveau!r}")
    return prompt.replace("{{NIVEAU}}", niveau_text)


def _chat_with_retry(model: str, message_content: str, context_label: str) -> str:
    return chat_with_major_error_fallback(
        ollama_model=model,
        message_content=message_content,
        context_label=context_label,
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )


def fiche_cadrage(sujet: str, niveau: str):
    sujet = _normalize_sujet(sujet)
    if not isinstance(niveau, str) or not niveau.strip():
        raise ValueError("Le niveau de prompt doit etre une chaine non vide.")

    input_path = INPUT_DIR / "fc_prompt.txt"

    prompt = _read_text(input_path, f"prompt {niveau}")
    prompt = _apply_prompt_variables(prompt, niveau)

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
