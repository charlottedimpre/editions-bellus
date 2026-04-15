from pathlib import Path
from typing import Any

from ollama import chat
from ollama import ChatResponse
from parser import parse_fiche_cadrage, read_text_file, to_json_file

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


def fiche_cadrage(sujet: str, niveau: str):
    sujet = _normalize_sujet(sujet)
    if not isinstance(niveau, str) or not niveau.strip():
        raise ValueError("Le niveau de prompt doit etre une chaine non vide.")

    input_path = INPUT_DIR / f"{niveau}.txt"

    prompt = _read_text(input_path, f"prompt {niveau}")

    response: ChatResponse = chat(model="mistral-large-3:675b-cloud", messages=[
        {
            "role": "user",
            "content": f"{prompt}\n\nSUJET : {sujet}",
        },
    ])

    if response.message is None or not response.message.content:
        raise ValueError("Reponse vide du modele pour la fiche de cadrage.")

    parsed = parse_fiche_cadrage(response.message.content)
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


if __name__ == '__main__':
    fc()
