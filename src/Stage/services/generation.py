from ..models import ContenuSection, ProcessStatus
import json
from ollama import chat
from .infos import extraire_infos_section, ajout_bdd_infos
from .plan import recup_sections
import os
from .normalisation import *
from ..settings import BASE_DIR

from django.db import connection

def reset_contenu_sections():
    with connection.cursor() as cur:
        cur.execute("TRUNCATE contenu_sections RESTART IDENTITY CASCADE;")
    print("Reset contenu sections effectué")

def ajout_contenu_section_bdd(section_id, chapitre_id, contenu_section_json):
    print(contenu_section_json)
    ContenuSection.objects.create(
        section_id=section_id,
        chapitre_id=chapitre_id,
        contenu=contenu_section_json
    )


def generation_par_sections():
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    sections_json = recup_sections()  # string JSON
    sections_data = json.loads(sections_json)  # redevient un dict Python
    sections = sections_data["sections"] # récupère la liste

    sections_triees = sorted(sections, key=lambda x: (x["chapitre_id"], x["ordre"]))

    nb_total = len(sections_triees)
    compt = 0

    for fichier in sections_triees:
        if not recup_si_sections(fichier["id"], fichier["chapitre_id"]):
            print(fichier)
            status.message = f"Generation de la section {fichier['ordre']} du chapitre {fichier['chapitre_id']} ..."
            status.progress = compt / (nb_total * 100)
            status.save()
            generation_section(fichier["ordre"], fichier["chapitre_id"], fichier["id"], fichier["chapitre_id"])
        compt += 1

def generation_section(numero_section, numero_chapitre, section_id, chapitre_id):
    from .fonctions_globales import recup_fichiers, model
    prompt = os.path.join(BASE_DIR, 'Stage/prompts/ecriture_section.txt')
    file = open(prompt, 'r', encoding="utf-8")
    prompt = file.read()
    fichiers_a_recup = ["fiche_stratégique", "recherches", "plan"]
    data_needed = recup_fichiers(fichiers_a_recup)
    context_prompt: str = ""
    for data in data_needed:
        context_prompt = context_prompt + data

    print("Ecriture de la section", numero_section ,"du chapitre", numero_chapitre, "en cours")
    response = chat(
        model=model,
        messages=[{'role': 'user', 'content': (
            "{numero_section}" + str(numero_section) + "{/numero_section}" +
             "{numero_chapitre}"+ str(numero_chapitre) + "{/numero_chapitre}" + "{contexte}" + context_prompt + "{/contexte}" + prompt)}], )

    file.close()
    print("Longueur réponse:", len(response.message.content))
    print("Réponse brute:", repr(response.message.content[:500]))

    print(response.message.content)
    ajout_contenu_section_bdd(section_id, chapitre_id, safe_json(response.message.content)["contenu"])
    infos_json = extraire_infos_section(response.message.content,numero_chapitre,numero_section)
    ajout_bdd_infos(infos_json)
    return safe_json(response.message.content)


def recup_si_sections(section_id, chapitre_id):
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute("""
                    SELECT contenu from contenu_sections WHERE section_id = %s and chapitre_id = %s;
                    """, (section_id, chapitre_id))
        contenu = cur.fetchone()
        if contenu:
            return True
        else:
            return False

def recup_contenu_sections_bdd():
    contenu = list(ContenuSection.objects.values("section_id", "chapitre_id", "contenu"))
    return json.dumps({"contenu_sections": contenu}, ensure_ascii=False, indent=2)