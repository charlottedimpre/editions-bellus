import json
from ollama import chat
from ..models import Chapitre, Section, NotionIndispensable
import os
from .normalisation import *
from ..settings import BASE_DIR
from .json_cleaner import clean_json, PLAN_SCHEMA, PLAN_VERIF_SCHEMA, filtrer_champs_valides, clean_champs


def creation_plan():
    from .fonctions_globales import recup_fichiers, model
    prompt = os.path.join(BASE_DIR, 'Stage/prompts/plan.txt')
    file = open(prompt, 'r', encoding="utf-8")
    prompt_plan = file.read()
    fichiers_a_recup = ["fiche_strategique", "recherches"]
    data_needed = recup_fichiers(fichiers_a_recup)
    context_prompt : str = ""
    for data in data_needed:
        context_prompt = context_prompt + data
    response = chat(
        model=model,
        messages=[{'role': 'user', 'content': context_prompt + prompt_plan }],
    )
    return response.message.content

def ajout_bdd_plan(plan_brut):
    data = safe_json(plan_brut)
    data = clean_json(data,PLAN_SCHEMA)
    for chapitre_data in data["chapitres"]:
        chapitre = Chapitre.objects.create(
            ordre=chapitre_data["ordre"],
            titre=chapitre_data["titre"],
            rôle_du_chapitre=chapitre_data["rôle_du_chapitre"],
            périmètre_thématique=chapitre_data["périmètre_thématique"],
            exclusions_thématiques=chapitre_data["exclusions_thématiques"],
            justification_indépendance_chapitre=chapitre_data["justification_indépendance_chapitre"]
        )

        for section_data in chapitre_data["sections"]:
            section = Section.objects.create(
                chapitre=chapitre,
                ordre=section_data["ordre"],
                titre=section_data["titre"],
                objectif_pédagogique=section_data["objectif_pédagogique"],
                périmètre_thématique=section_data["périmètre_thématique"],
                exclusions_thématiques=section_data["exclusions_thématiques"],
                message_clé_à_retenir=section_data["message_clé_à_retenir"],
                angle_rhétorique=section_data.get("angle_rhétorique"),
                nombre_de_mots_cible=section_data.get("nombre_de_mots_cible")
            )

            for notion in section_data.get("notions", []):
                NotionIndispensable.objects.create(
                    nom_de_la_notion=notion["nom_de_la_notion"],
                    contenu_de_la_notion=notion["contenu_de_la_notion"],
                    section=section,
                    placée=True
                )

    print("Plan inséré avec succès.")

def reset_plan():
    from django.db import connection as conn
    with conn.cursor() as cur:
        cur.execute("""
                            TRUNCATE sections RESTART IDENTITY CASCADE;
                        """)
        cur.execute("""
            TRUNCATE chapitres RESTART IDENTITY CASCADE;
        """)
        conn.commit()
        print("Reset plan effectué")

def recup_chapitres():
    chapitres = list(Chapitre.objects.values(
        "id", "ordre", "titre", "rôle_du_chapitre", "périmètre_thématique",
        "exclusions_thématiques", "justification_indépendance_chapitre", "statut"
    ))
    return json.dumps({"chapitres": chapitres}, ensure_ascii=False, indent=2)


def recup_sections():
    sections = list(Section.objects.values(
        "id", "chapitre_id", "ordre", "titre", "objectif_pédagogique",
        "périmètre_thématique",
        "exclusions_thématiques", "message_clé_à_retenir", "nombre_de_mots_cible"
    ))
    return json.dumps({"sections": sections}, ensure_ascii=False, indent=2)

def verifcation_plan():
    from .fonctions_globales import recup_fichiers, model
    prompt = os.path.join(BASE_DIR, 'Stage/prompts/verification_plan.txt')
    file = open(prompt, 'r', encoding="utf-8")
    prompt = file.read()
    fichiers_a_recup = ["fiche_stratégique", "recherches", "plan"]
    data_needed = recup_fichiers(fichiers_a_recup)
    context_prompt: str = ""
    for data in data_needed:
        context_prompt = context_prompt + data

    response = chat(
        model=model,
        messages=[{'role': 'user', 'content': (
                "{contexte}" + context_prompt + "{/contexte}" + prompt)}], )

    file.close()
    print(response.message.content)
    return response.message.content

def modif_post_verif_plan(json_modifs):
    if json_modifs == "true" or json_modifs is True:
        print("Plan cohérent, aucune modification nécessaire")
        return

    json_modifs = safe_json(json_modifs)
    json_modifs = clean_json(json_modifs, PLAN_VERIF_SCHEMA)

    if not isinstance(json_modifs, dict):
        print("❌ JSON invalide")
        return

    reparations = json_modifs.get("reparation", [])

    if not isinstance(reparations, list):
        print("❌ 'reparation' invalide")
        return

    TABLE_MAP = {
        "chapitres": Chapitre,
        "sections": Section,
    }

    for modif in reparations:
        action = modif.get("action")
        table = modif.get("table")
        model_class = TABLE_MAP.get(table)

        if not model_class:
            print("⚠️ table inconnue:", table)
            continue

        champs = clean_champs(table, modif.get("champs_a_modifier", {}))

        if not champs:
            print("⚠️ aucun champ valide après filtrage")
            continue

        obj_id = modif.get("id")

        try:
            if action in ("modifier", "déplacer"):
                model_class.objects.filter(id=obj_id).update(**champs)

            elif action == "supprimer":
                model_class.objects.filter(id=obj_id).delete()

            elif action == "ajouter":
                model_class.objects.create(**champs)

            elif action == "fusionner":
                id_a_supprimer = champs.get("supprimer_id")
                if id_a_supprimer:
                    model_class.objects.filter(id=id_a_supprimer).delete()

        except Exception as e:
            print("❌ erreur Django:", e)


def demande_cadrage_mots_par_sections():
    from .fonctions_globales import recup_fichiers, model
    prompt = os.path.join(BASE_DIR, 'Stage/prompts/cadrage_mots_par_section.txt')
    file = open(prompt, 'r', encoding="utf-8")
    prompt = file.read()
    fichiers_a_recup = ["fiche_stratégique", "recherches", "plan"]
    data_needed = recup_fichiers(fichiers_a_recup)
    context_prompt: str = ""
    for data in data_needed:
        context_prompt = context_prompt + data

    response = chat(
        model=model,
        messages=[{'role': 'user', 'content': (
                    "{contexte}" + context_prompt + "{/contexte}" + prompt )}],)

    file.close()
    print(response.message.content)
    return safe_json(response.message.content)

def cadrage_mots_par_sections(json_sections):
    print("Total mots actuel = ", json_sections["total_mots"])
    for section in json_sections["sections"]:
        Section.objects.filter(id=section["id"]).update(
            nombre_de_mots_cible=section["nombre_de_mots_cible"]
        )
