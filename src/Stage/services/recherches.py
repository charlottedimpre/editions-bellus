from typing import List
import json
from ollama import chat
from ..models import *
import os.path
from .normalisation import *
from ..settings import BASE_DIR


def reset_recherches():
    IdeeRecherchee.objects.all().delete()
    NotionIndispensable.objects.all().delete()
    ErreurFrequente.objects.all().delete()
    Risque.objects.all().delete()
    EtapeEssentielle.objects.all().delete()
    print("Reset recherches effectué")

def recherches_ia_et_ajout_bdd():
    from .fonctions_globales import model, recup_fichiers

    fichiers_a_recup : List = ["fiche_strategique"]
    entrees = recup_fichiers(fichiers_a_recup)
    prompt = os.path.join(BASE_DIR, 'Stage/prompts/recherches.txt')
    file = open(prompt, 'r')
    prompt_recherche = file.read()
    response = chat(
        model=model,
        messages=[{'role' : 'user',
                     'content' : (entrees[0] + prompt_recherche)}])
    print(response.message.content)
    ajout_bdd_recherches(response.message.content)

def ajout_bdd_recherches(recherches_brut):
    data = safe_json(recherches_brut)

    for idee in data["idees_recherchees"]:
        IdeeRecherchee.objects.create(contenu_de_l_idée=idee["contenu"])

    for notion in data["notions_indispensables"]:
        nom = notion.get("nom", "Sans nom")  # <-- changement ici
        NotionIndispensable.objects.create(
            nom_de_la_notion=nom,             # <-- et ici
            contenu_de_la_notion=notion["contenu"]
        )

    for erreur in data["erreurs_frequentes"]:
        ErreurFrequente.objects.create(contenu_de_l_erreur=erreur["contenu"])

    for etape in data["etapes_essentielles"]:
        EtapeEssentielle.objects.create(contenu_de_l_etapes=etape["contenu"])

    for risque in data["risques"]:
        Risque.objects.create(contenu_du_risque=risque["contenu"])



def recup_idees():
    idees = list(IdeeRecherchee.objects.values("contenu_de_l_idée", "placée", "section_id"))
    return json.dumps({"idees_recherchees": idees}, ensure_ascii=False, indent=2)


def recup_notions():
    notions = list(NotionIndispensable.objects.values("nom_de_la_notion", "contenu_de_la_notion", "placée", "section_id"))
    return json.dumps({"notions_indispensables": notions}, ensure_ascii=False, indent=2)

def recup_erreurs_frequentes():
    erreurs = list(ErreurFrequente.objects.values("contenu_de_l_erreur", "placée", "section_id"))
    return json.dumps({"erreurs_frequentes": erreurs}, ensure_ascii=False, indent=2)


def recup_etapes_essentielles():
    etapes = list(EtapeEssentielle.objects.values("contenu_de_l_etapes", "placée", "section_id"))
    return json.dumps({"etapes_essentielles": etapes}, ensure_ascii=False, indent=2)


def recup_risque():
    risques = list(Risque.objects.values("contenu_du_risque", "placée", "section_id"))
    return json.dumps({"risque": risques}, ensure_ascii=False, indent=2)

def recup_recherches():
    recherches : list = []
    recherches.append(recup_idees())
    recherches.append(recup_notions())
    recherches.append(recup_erreurs_frequentes())
    recherches.append(recup_etapes_essentielles())
    recherches.append(recup_risque())
    return recherches