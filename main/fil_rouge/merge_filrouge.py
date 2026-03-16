import json
import os

from ollama import chat, ChatResponse

def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    structure_path = os.path.join("..", "structure_chapitre", "output", "structure_chapitre.json")
    with open(structure_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_insertion(fil_rouge_data: dict, chapitre: int, section: int) -> str:
    for ins in fil_rouge_data.get("insertions", []):
        if int(ins.get("chapitre", -1)) == int(chapitre) and int(ins.get("section", -1)) == int(section):
            return ins.get("contenu", "")
    return ""


def incorporer(chapitre, section):
    prompt_path = os.path.join("input", "mf_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()


    section_path = os.path.join("..", "section", "output", "section", f"section_ch{chapitre}_s{section}.json")
    with open(section_path, "r", encoding="utf-8") as f:
        section_data = json.load(f)  # mieux que f.read()

    fil_rouge_path = os.path.join("output", "fil_rouge.json")
    with open(fil_rouge_path, "r", encoding="utf-8") as f:
        fil_rouge_data = json.load(f)

    exemple = get_insertion(fil_rouge_data, chapitre, section)



    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nSECTION : {section_data.get('contenu', '')}\n\nFIL ROUGE : {exemple}\n\nNUMERO CHAPITRE : {chapitre}\n\nNUMERO SECTION : {section}',
        },
    ])
    return response.message.content


def merge_filrouge_wrapper():
    chapitres = load_structure()
    for chapitre in chapitres:
        for section in chapitre.get("sections", []):
            result = incorporer(chapitre["numero"], section["numero"])
            print(f"Résultat pour Chapitre {chapitre['numero']} Section {section['numero']} :\n{result}\n{'-'*80}\n")

            filename = f"section_ch{chapitre}_s{section}.json"
            filepath = os.path.join("..", "section", "output", "section", filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    merge_filrouge_wrapper()