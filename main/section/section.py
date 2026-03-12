import json
import os

from ollama import ChatResponse, chat

from parser import parse_section


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    structure_path = os.path.join("..", "structure_chapitre", "output", "structure_chapitre.json")
    with open(structure_path, "r", encoding="utf-8") as f:
        return json.load(f)


def gen_section(chapitre, section):
    """Génère une section et la sauvegarde dans output/section_ch{X}_s{Y}.json."""

    fiche_path = os.path.join("..", "fiche_cadrage", "output", "fiche_cadrage.json")
    with open(fiche_path, "r", encoding="utf-8") as f:
        fiche = f.read()

    plan_path = os.path.join("..", "plan_detaille", "output", "plan_detaille.json")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = f.read()

    structure_path = os.path.join("..", "structure_chapitre", "output", "structure_chapitre.json")
    with open(structure_path, "r", encoding="utf-8") as f:
        structure = f.read()

    prompt_path = os.path.join("input", "s_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\nFICHE DE STRUCTURE DU CHAPITRE : {structure}\n\nCHAPITRE À RÉDIGER : Chapitre {chapitre}\n\nSECTION À RÉDIGER : Section {section}',
        },
    ])

    parsed = parse_section(response.message.content, chapitre, section)
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = os.path.join("output", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"   Section {section} du chapitre {chapitre} sauvegardée → {filename}")


def gen_all_sections():
    """Parcourt tous les chapitres et sections de structure_chapitre.json et génère chaque section."""
    chapitres = load_structure()
    nb_chapitres = len(chapitres)
    nb_total_sections = sum(len(ch["sections"]) for ch in chapitres)

    print(f"Structure chargée : {nb_chapitres} chapitres, {nb_total_sections} sections au total\n")

    for chap in chapitres:
        ch_num = int(chap["numero"])
        nb_sec = len(chap["sections"])
        print(f"Chapitre {ch_num} — {chap['titre']} ({nb_sec} sections)")

        for sec in chap["sections"]:
            sec_num = int(sec["numero"])
            gen_section(ch_num, sec_num)

    print(f"\nGénération terminée : {nb_total_sections} sections générées pour {nb_chapitres} chapitres.")


if __name__ == '__main__':
    gen_all_sections()
