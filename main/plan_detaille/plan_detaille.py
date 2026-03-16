import json
import os

from ollama import ChatResponse, chat

from parser import parse_plan_detaille


def plan_detail():
    input_path = os.path.join("input", "pd_prompt.txt")
    with open(input_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    fc_path = os.path.join("..", "fiche_cadrage", "output", "fiche_cadrage.json")
    with open(fc_path, "r", encoding="utf-8") as f:
        fiche_cadrage = f.read()

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE : {fiche_cadrage}',
        },
    ])
    parsed = parse_plan_detaille(response.message.content)
    filepath = os.path.join("output", "plan_detaille.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    plan_detail()