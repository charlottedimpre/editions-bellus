from ..models import FicheStrategique
from .normalisation import *
from ollama import chat
import json

def transformation_sujet_en_fiche_strat(sujet):
    response = chat(
        model='kimi-k2.5:cloud',
        messages=[{'role': 'user',
                   'content': (
                               "Tu es un expert en ingénierie éditoriale. Ton rôle est de transformer un sujet brut en une fiche stratégique structurée pour guider la rédaction d'un livre."
                               "---"
                               "## SUJET BRUT"
                               + sujet +
                               "---"
                               "Analyse le sujet et génère une fiche stratégique complète. Sois précis, concis et opérationnel — chaque champ doit guider concrètement la rédaction."
                               "---"
                               "Réponds UNIQUEMENT avec ce JSON, sans texte avant ni après :"

                               "{"
                               '"sujet_précis": "formulation précise et délimitée du sujet",'
                               '"cible": "description précise du lecteur cible (profil, niveau, besoin)",'
                               '"niveau": "débutant | intermédiaire | avancé",'
                               '"objectif_lecteur": "ce que le lecteur sera capable de faire ou comprendre après lecture",'
                               '"logique_ordre_des_chapitres": "chronologique | thématique | progressif | problème-solution",'
                               '"sujets_exclus_du_livre": "sujets connexes volontairement exclus et pourquoi",'
                               '"contraintes_éditoriales": "ton, style, longueur cible, contraintes particulières"'
                               '}'
                               '}],'
                               "Réponds UNIQUEMENT avec le JSON brut. "
                               "N'utilise pas de balises markdown, pas de ```json, pas de ```, pas d'explication. "
                               "Le premier caractère de ta réponse doit être { et le dernier }."
                               )}], )
    return response.message.content

def ajout_bdd_fiche_strat(fiche_strat):
    fiche_strat_json = safe_json(fiche_strat)
    FicheStrategique.objects.create(
        sujet_précis=fiche_strat_json['sujet_précis'],
        cible=fiche_strat_json['cible'],
        niveau=fiche_strat_json['niveau'],
        objectif_lecteur=fiche_strat_json['objectif_lecteur'],
        logique_ordre_des_chapitres=fiche_strat_json['logique_ordre_des_chapitres'],
        sujets_exclus_du_livre=fiche_strat_json['sujets_exclus_du_livre'],
        contraintes_éditoriales=fiche_strat_json['contraintes_éditoriales']
    )

from django.db import connection

def reset_fiche_strat():
    with connection.cursor() as cur:
        cur.execute("TRUNCATE fiche_strategique RESTART IDENTITY CASCADE;")
    print("Reset fiche strategique effectué")


def recup_fiche_strat():
    fiche = FicheStrategique.objects.first()
    # Retourne le même format JSON qu'avant pour ne pas casser le reste
    return json.dumps({"fiche_stratégique": [{
        "sujet_précis": fiche.sujet_précis,
        "cible": fiche.cible,
        "niveau": fiche.niveau,
        "objectif_lecteur": fiche.objectif_lecteur,
        "logique_ordre_des_chapitres": fiche.logique_ordre_des_chapitres,
        "sujets_exclus_du_livre": fiche.sujets_exclus_du_livre,
        "contraintes_éditoriales" : fiche.contraintes_éditoriales
    }]}, ensure_ascii=False, indent=2)