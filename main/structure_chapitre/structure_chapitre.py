import json
import os

from ollama import ChatResponse, chat

from parser import parse_structure_chapitres


def structure_chapitre():
    fiche_path = os.path.join("..", "fiche_cadrage", "output", "fiche_cadrage.json")
    with open(fiche_path, "r", encoding="utf-8") as f:
        fiche_raw = f.read()

    plan_path = os.path.join("..", "plan_detaille", "output", "plan_detaille.json")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_raw = f.read()

    prompt_path = os.path.join("input", "sc_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DÉTAILLÉ :{plan_raw}',
        },
    ])
    parsed = parse_structure_chapitres(response.message.content)
    filepath = os.path.join("output", "structure_chapitre.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    structure_chapitre()