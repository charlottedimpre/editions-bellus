from pathlib import Path

from ollama import chat
from ollama import ChatResponse
from parser import parse_fiche_cadrage, to_json_file

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fiche_cadrage(sujet: str, niveau: str):
    print(sujet)
    input_path = INPUT_DIR / f"{niveau}.txt"

    with input_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nSUJET : {sujet}',
        },
    ])
    parsed = parse_fiche_cadrage(response.message.content)
    return parsed


def fc():
    fichier = ["fc_debutant", "fc_intermediaire", "fc_avance"]

    sujet = input("Quel est le sujet de votre livre ? ")
    while len(sujet) < 1:
        print("Le sujet ne peut pas être vide.")
        sujet = input("Quel est le sujet de votre livre ? ")

    niveau_input = input("Quel niveau souhaitez-vous ? (1 - Débutant, 2 - Intermédiaire, 3 - Avancé) : ")

    while niveau_input not in ['1', '2', '3']:
        print("Le niveau doit être 1, 2 ou 3.")
        niveau_input = input("Quel niveau souhaitez-vous ? (1 - Débutant, 2 - Intermédiaire, 3 - Avancé) : ")

    txt = fiche_cadrage(sujet, fichier[int(niveau_input) - 1])
    print(f"Fiche de cadrage générée : {sujet} {fichier[int(niveau_input) - 1]}")
    to_json_file(txt, OUTPUT_DIR / "fiche_cadrage.json")


if __name__ == '__main__':
    fc()
