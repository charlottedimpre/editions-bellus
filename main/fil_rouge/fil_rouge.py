import json
import os

from ollama import ChatResponse, chat

from main.section.section import load_structure

from parser import parse_filrouge


def gen_filrouge():
    chapitres = load_structure()

    fiche_path = os.path.join("..", "fiche_cadrage", "output", "fiche_cadrage.json")
    with open(fiche_path, "r", encoding="utf-8") as f:
        fiche_raw = f.read()

    plan_path = os.path.join("..", "plan_detaille", "output", "plan_detaille.json")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_raw = f.read()

    resume = []
    for chapitre in chapitres:
        for section in chapitre["sections"]:
            coherence_path = os.path.join("..", "section", "resume", f"coherence_ch{chapitre['numero']}_s{section['numero']}.json")
            with open(coherence_path, "r", encoding="utf-8") as f:
                coherence_raw = f.read()
            resume.append(coherence_raw)

    prompt_path = os.path.join("input", "fr_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DÉTAILLÉ :{plan_raw}\n\nRÉSUMÉ DES CHAPITRES RÉDIGÉS :{resume}',
        },
    ])
    parsed = parse_filrouge(response.message.content)
    filepath = os.path.join("output", "fil_rouge.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    gen_filrouge()
