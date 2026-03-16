import json
import os

from ollama import ChatResponse, chat

from parser import parse_section


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    structure_path = os.path.join("..", "structure_chapitre", "output", "structure_chapitre.json")
    with open(structure_path, "r", encoding="utf-8") as f:
        return json.load(f)

def coherence_check(chapitre, section):
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = os.path.join("output", "section", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        fiche = f.read()

    prompt_path = os.path.join("input", "c_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nSection à étudier :{fiche}',
        },
    ])
    filename = f"coherence_ch{chapitre}_s{section}.json"
    filepath = os.path.join("output", "resume", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(response.message.content.strip(), f, ensure_ascii=False, indent=2)
    return response.message.content.strip()


def gen_section(chapitre, section):
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

    if chapitre == 1 and section == 1:
        coherence = "il n'y a pas de section précédente, c'est la première section du premier chapitre, aucune vérification de cohérence nécessaire."
        print(f"{coherence}")
    elif section == 1:
        chapitres = load_structure()
        for chap in chapitres:
            if int(chap["numero"]) == chapitre - 1:
                nb_sec = len(chap["sections"])

        coherence_path = os.path.join("output", "resume", f"coherence_ch{chapitre - 1}_s{nb_sec}.json")
        with open(coherence_path, "r", encoding="utf-8") as f:
            coherence = f.read()
        print(f"Vérification de cohérence avec la section précédente : coherence_ch{chapitre - 1}_s{nb_sec}.json...")
    else:
        coherence_path = os.path.join("output", "resume", f"coherence_ch{chapitre}_s{section - 1}.json")
        with open(coherence_path, "r", encoding="utf-8") as f:
            coherence = f.read()
        print (f"Vérification de cohérence avec la section précédente : coherence_ch{chapitre}_s{section - 1}.json...")



    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\nFICHE DE STRUCTURE DU CHAPITRE : {structure}\n\nCHAPITRE À RÉDIGER : Chapitre {chapitre}\n\nSECTION À RÉDIGER : Section {section}\n\n\nVérification de cohérence avec la section précédente : {coherence}',
        },
    ])

    parsed = parse_section(response.message.content, chapitre, section)
    filename = f"section_ch{chapitre}_s{section}.json"
    filepath = os.path.join("output", "section", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"Section {section} du chapitre {chapitre} sauvegardée → {filename}")

    coherence_check(chapitre, section)

    print("Vérification de cohérence effectuée pour la section précédente.")


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
            try :
                gen_section(ch_num, sec_num)
            except Exception as e :
                gen_section(ch_num, sec_num)



    print(f"\nGénération terminée : {nb_total_sections} sections générées pour {nb_chapitres} chapitres.")

def merge_chapter_sections(chapitre_num: int):
    """Fusionne tous les fichiers section_ch{X}_s{Y}.json d'un chapitre dans un seul chapitre_{X}.json."""
    chapitres = load_structure()
    chapitre_data = None
    for chap in chapitres:
        if int(chap["numero"]) == chapitre_num:
            chapitre_data = chap
            break

    if chapitre_data is None:
        print(f"Chapitre {chapitre_num} introuvable dans structure_chapitre.json")
        return

    sections = []
    for sec in chapitre_data["sections"]:
        sec_num = int(sec["numero"])
        filepath = os.path.join("output", "section", f"section_ch{chapitre_num}_s{sec_num}.json")
        if not os.path.exists(filepath):
            print(f"   Fichier manquant : {filepath}")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        sections.append({
            "section": sec_num,
            "titre": sec.get("titre_section", ""),
            "contenu": data["contenu"],
        })

    result = {
        "chapitre": chapitre_num,
        "titre": chapitre_data["titre"],
        "nb_sections": len(sections),
        "sections": sections,
    }

    output_path = os.path.join("output", "chapitre", f"chapitre_{chapitre_num}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Chapitre {chapitre_num} fusionné -> {output_path} ({len(sections)} sections)")

def merge_all_chapters():
    """Fusionne les sections de chaque chapitre dans un fichier chapitre_{X}.json."""
    chapitres = load_structure()
    print(f"Fusion des sections pour {len(chapitres)} chapitres...\n")
    for chap in chapitres:
        merge_chapter_sections(int(chap["numero"]))
    print(f"\nFusion terminée.")



if __name__ == '__main__':
    gen_all_sections()
    merge_all_chapters()
