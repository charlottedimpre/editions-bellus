from typing import List

from ollama import chat
#import time as t
import json
import psycopg
from psycopg.sql import NULL
from pyexpat.errors import messages

model = "kimi-k2.5:cloud"

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="editorial_engine",
    user="postgres",
    password="postgres"
)
print("Initialisation BDD faite")

def transformation_sujet_en_fiche_strat(sujet):
    response = chat(
        model='kimi-k2.5:cloud',
        messages=[{'role': 'user',
                   'content': ("Tu es un expert en ingénierie éditoriale. Ton rôle est de transformer un sujet brut en une fiche stratégique structurée pour guider la rédaction d'un livre."
                                "---"
                                "## SUJET BRUT"
                                +sujet+
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
                               )}],)
    return response.message.content

def ajout_bdd_fiche_strat(fiche_strat):
    fiche_strat_json = json.loads(fiche_strat)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fiche_strategique (sujet_précis,cible,niveau,objectif_lecteur,logique_ordre_des_chapitres,sujets_exclus_du_livre,contraintes_éditoriales )
            VALUES (%s, %s,%s,%s,%s,%s,%s)
            """,
            (fiche_strat_json["sujet_précis"], fiche_strat_json["cible"], fiche_strat_json["niveau"], fiche_strat_json["objectif_lecteur"], fiche_strat_json["logique_ordre_des_chapitres"], fiche_strat_json["sujets_exclus_du_livre"],fiche_strat_json["contraintes_éditoriales"])
        )
    conn.commit()

def recup_bdd_fiche_strat():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                           'sujet_précis', sujet_précis,
                                           'cible', cible,
                                            'niveau', niveau,
                                            'objectif_lecteur', objectif_lecteur,
                                            'logique_ordre_des_chapitres', logique_ordre_des_chapitres,
                                            'sujets_exclus_du_livre', sujets_exclus_du_livre,
                                            'contraintes_éditoriales',contraintes_éditoriales
                                   )
                           )
                    FROM fiche_strategique;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"fiche_stratégique": result}, ensure_ascii=False, indent=2)

def verif_humaine(truc_a_verif):
    print("Vérification humaine demandée :")
    print(truc_a_verif)
    print("y ou n ?")
    reponse = input("Entrez une valeur : ")
    if reponse == "y":
        print("Etape validée")
        return True
    else:
        print("Etape refusée")
        return False

def reset_fiche_strat():
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE fiche_strategique RESTART IDENTITY;
        """)
        conn.commit()
        print("Reset fiche strategique effectué")

def reset_recherches():
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE idees_recherchees RESTART IDENTITY;
        """)
        cur.execute("""
                    TRUNCATE notions_indispensables RESTART IDENTITY;
                """)
        cur.execute("""
                    TRUNCATE erreurs_frequentes RESTART IDENTITY;
                """)
        cur.execute("""
                    TRUNCATE etapes_essentielles RESTART IDENTITY;
                """)
        cur.execute("""
                    TRUNCATE risque RESTART IDENTITY;
                """)
        conn.commit()
        print("Reset recherches effectué")

def reset_plan():
    with conn.cursor() as cur:
        cur.execute("""
                            TRUNCATE sections RESTART IDENTITY CASCADE;
                        """)
        cur.execute("""
            TRUNCATE chapitres RESTART IDENTITY CASCADE;
        """)
        conn.commit()
        print("Reset plan effectué")

def reset_contenu_sections():
    with conn.cursor() as cur:
        cur.execute("""
        TRUNCATE contenu_sections RESTART IDENTITY CASCADE;
        """)
        conn.commit()
        print("Reset contenu sections effectué")

def recup_fichiers(fichiers_a_recup : List):
    fichiers_renvoyes : List = []
    with conn.cursor() as cur:
        for fichier in fichiers_a_recup:
            if fichier in fichiers_a_recup:
                if fichier == "fiche_strategique":
                    fichiers_renvoyes.append(recup_bdd_fiche_strat())
                if fichier == "recherches":
                    recherches = recup_recherches()
                    for recherche in recherches:
                        fichiers_renvoyes.append(recherche)
                if fichier == "plan":
                    fichiers_renvoyes.append(recup_chapitres())
                    fichiers_renvoyes.append(recup_sections())
                if fichier == "infos":
                    infos = recup_infos()
                    for info in infos:
                        fichiers_renvoyes.append(info)


    return fichiers_renvoyes

def recherches_ia_et_ajout_bdd():
    fichiers_a_recup : List = ["fiche_strategique"]
    entrees = recup_fichiers(fichiers_a_recup)
    file = open("prompt_test/recherches.txt", 'r')
    prompt_recherche = file.read()
    response = chat(
        model='kimi-k2.5:cloud',
        messages=[{'role' : 'user',
                     'content' : (entrees[0] + prompt_recherche)}])
    print(response.message.content)
    ajout_bdd_recherches(response.message.content)

def ajout_bdd_recherches(recherches_brut):
    data = json.loads(recherches_brut)

    with conn.cursor() as cur:
        for idee in data["idees_recherchees"]:
            cur.execute(
                "INSERT INTO idees_recherchees (contenu_de_l_idée) VALUES (%s)",
                (idee["contenu"],)
            )
        for notion in data["notions_indispensables"]:
            cur.execute(
                "INSERT INTO notions_indispensables (nom_de_la_notion, contenu_de_la_notion) VALUES (%s, %s)",
                (notion["nom"], notion["contenu"])
            )
        for erreur in data["erreurs_frequentes"]:
            cur.execute(
                "INSERT INTO erreurs_frequentes (contenu_de_l_erreur) VALUES (%s)",
                (erreur["contenu"],)
            )
        for etape in data["etapes_essentielles"]:
            cur.execute(
                "INSERT INTO etapes_essentielles (contenu_de_l_etapes) VALUES (%s)",
                (etape["contenu"],)
            )
        for risque in data["risques"]:
            cur.execute(
                "INSERT INTO risque (contenu_du_risque) VALUES (%s)",
                (risque["contenu"],)
            )
    conn.commit()


def recup_idees():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                           'contenu_de_l_idée', contenu_de_l_idée,
                                            'placée', placée,
                                            'section_id', section_id 
                                   )
                           )
                    FROM idees_recherchees;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"idees_recherchees": result}, ensure_ascii=False, indent=2)

def recup_notions():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                            'nom_de_la_notion', nom_de_la_notion,
                                           'contenu_de_la_notion', contenu_de_la_notion,
                                            'placée', placée,
                                            'section_id', section_id 
                                   )
                           )
                    FROM notions_indispensables;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"notions_indispensables": result}, ensure_ascii=False, indent=2)

def recup_erreurs_frequentes():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                           'contenu_de_l_erreur', contenu_de_l_erreur,
                                            'placée', placée,
                                            'section_id', section_id 
                                   )
                           )
                    FROM erreurs_frequentes;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"erreurs_frequents": result}, ensure_ascii=False, indent=2)

def recup_etapes_essentielles():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                           'contenu_de_l_etapes', contenu_de_l_etapes,
                                            'placée', placée,
                                            'section_id', section_id 
                                   )
                           )
                    FROM etapes_essentielles;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"etapes_essentielles": result}, ensure_ascii=False, indent=2)

def recup_risque():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                           'contenu_du_risque', contenu_du_risque,
                                            'placée', placée,
                                            'section_id', section_id 
                                   )
                           )
                    FROM risque;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"risque": result}, ensure_ascii=False, indent=2)

def recup_recherches():
    recherches : list = []
    recherches.append(recup_idees())
    recherches.append(recup_notions())
    recherches.append(recup_erreurs_frequentes())
    recherches.append(recup_etapes_essentielles())
    recherches.append(recup_risque())
    return recherches

def creation_plan():
    file = open("prompt_test/plan.txt", 'r', encoding="utf-8")
    prompt_plan = file.read()
    fichiers_a_recup = ["fiche_strategique", "recherches"]
    data_needed = recup_fichiers(fichiers_a_recup)
    context_prompt : str = ""
    for data in data_needed:
        context_prompt = context_prompt + data
    response = chat(
        model='kimi-k2.5:cloud',
        messages=[{'role': 'user', 'content': context_prompt + prompt_plan }],
    )
    return response.message.content

def ajout_bdd_plan(plan_brut):
    data = json.loads(plan_brut)

    with conn.cursor() as cur:
        for chapitre in data["chapitres"]:
            # Insertion du chapitre
            cur.execute("""
                        INSERT INTO chapitres (ordre,
                                               titre,
                                               rôle_du_chapitre,
                                               périmètre_thématique,
                                               exclusions_thématiques,
                                               justification_indépendance_chapitre)
                        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                        """, (
                            chapitre["ordre"],
                            chapitre["titre"],
                            chapitre["rôle_du_chapitre"],
                            chapitre["périmètre_thématique"],
                            chapitre["exclusions_thématiques"],
                            chapitre["justification_indépendance_chapitre"]
                        ))
            chapitre_id = cur.fetchone()[0]

            # Insertion des sections
            for section in chapitre["sections"]:
                cur.execute("""
                            INSERT INTO sections (chapitre_id,
                                                  ordre,
                                                  titre,
                                                  objectif_pédagogique,
                                                  périmètre_thématique,
                                                  exclusions_thématiques,
                                                  message_clé_à_retenir,
                                                  angle_rhétorique,
                                                  nombre_de_mots_cible)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                            """, (
                                chapitre_id,
                                section["ordre"],
                                section["titre"],
                                section["objectif_pédagogique"],
                                section["périmètre_thématique"],
                                section["exclusions_thématiques"],
                                section["message_clé_à_retenir"],
                                section.get("angle_rhétorique"),
                                section.get("nombre_de_mots_cible")
                            ))
                section_id = cur.fetchone()[0]

                # Insertion des notions liées à la section
                for notion in section.get("notions", []):
                    cur.execute("""
                                INSERT INTO notions_indispensables (nom_de_la_notion,
                                                                    contenu_de_la_notion,
                                                                    section_id,
                                                                    placée)
                                VALUES (%s, %s, %s, TRUE)
                                """, (
                                    notion["nom_de_la_notion"],
                                    notion["contenu_de_la_notion"],
                                    section_id
                                ))

    conn.commit()
    print("Plan inséré avec succès.")

def recup_chapitres():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                            'id', id,
                                            'ordre', ordre,
                                           'titre', titre,
                                            'rôle_du_chapitre', rôle_du_chapitre,
                                            'périmètre_thématique', périmètre_thématique,
                                            'exclusions_thématiques', exclusions_thématiques,
                                            'justification_indépendance_chapitre',  justification_indépendance_chapitre,
                                            'statut', statut
                                   )
                           )
                    FROM chapitres;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"chapitres": result}, ensure_ascii=False, indent=2)

def recup_sections():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                            'id', id,
                                           'chapitre_id', chapitre_id,
                                            'ordre', ordre,
                                            'titre', titre,
                                            'objectif_pédagogique', objectif_pédagogique,
                                            'exclusions_thématiques' , exclusions_thématiques, 
                                            'message_clé_à_retenir',  message_clé_à_retenir,
                                            'nombre_de_mots_cible', nombre_de_mots_cible
                                   )
                           )
                    FROM sections;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"sections": result}, ensure_ascii=False, indent=2)

def recup_glossaire():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                            'id', id,
                                           'terme', terme,
                                            'définition_utilisée_dans_ce_livre', définition_utilisée_dans_ce_livre,
                                            'mise_en_garde_sur_ce_terme', mise_en_garde_sur_ce_terme
                                   )
                           )
                    FROM glossaire;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"glossaire": result}, ensure_ascii=False, indent=2)

def recup_exemples():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                            'id', id,
                                           'titre_de_l_exemple', titre_de_l_exemple,
                                            'description_complète_de_l_exemple', description_complète_de_l_exemple,
                                            'chiffres_ou_données_utilisés', chiffres_ou_données_utilisés,
                                            'source_ou_origine', source_ou_origine 
                                   )
                           )
                    FROM exemples;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"exemples": result}, ensure_ascii=False, indent=2)

def recup_affirmations():
    with conn.cursor() as cur:
        cur.execute("""
                    SELECT json_agg(
                                   json_build_object(
                                            'id', id,
                                           'contenu_de_l_affirmation', contenu_de_l_affirmation,
                                            'type_affirmation', type_affirmation,
                                            'à_ne_pas_contredire', à_ne_pas_contredire
                                   )
                           )
                    FROM affirmations_posées;
                    """)
        result = cur.fetchone()[0]
    return json.dumps({"affirmations_posées": result}, ensure_ascii=False, indent=2)

def recup_infos():
    infos : list = []
    infos.append(recup_glossaire())
    infos.append(recup_exemples())
    infos.append(recup_affirmations())
    return infos

def demande_cadrage_mots_par_sections():
    file = open("prompt_test/cadrage_mots_par_section.txt", 'r', encoding="utf-8")
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
    return json.loads(response.message.content)

def cadrage_mots_par_sections(json_sections):
    print("Total mots actuel = ", json_sections["total_mots"])
    for section in json_sections["sections"]:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sections set nombre_de_mots_cible = (%s) where id = (%s);
            """,
            (section["nombre_de_mots_cible"], section["id"])
            )
        conn.commit()

def verifcation_plan():
    file = open("prompt_test/verification_plan.txt", 'r', encoding="utf-8")
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
    return json.loads(response.message.content)

def modif_post_verif_plan(json_modifs):
    if json_modifs == "true" or json_modifs is True:
        print("Plan cohérent, aucune modification nécessaire")
        return

    with conn.cursor() as cur:
        for modif in json_modifs["reparation"]:
            action = modif["action"]

            if action == "modifier" or action == "déplacer":
                # UPDATE : on modifie les champs indiqués
                for champ, valeur in modif["champs_a_modifier"].items():
                    cur.execute(
                        f"UPDATE {modif['table']} SET {champ} = %s WHERE id = %s",
                        (valeur, modif["id"])
                    )

            elif action == "supprimer":
                # DELETE : on supprime la ligne
                cur.execute(
                    f"DELETE FROM {modif['table']} WHERE id = %s",
                    (modif["id"],)
                )

            elif action == "ajouter":
                # INSERT : les champs_a_modifier contiennent les valeurs à insérer
                champs = list(modif["champs_a_modifier"].keys())
                valeurs = list(modif["champs_a_modifier"].values())
                colonnes = ", ".join(champs)
                placeholders = ", ".join(["%s"] * len(valeurs))
                cur.execute(
                    f"INSERT INTO {modif['table']} ({colonnes}) VALUES ({placeholders})",
                    valeurs
                )

            elif action == "fusionner":
                # Garde l'ID principal, supprime l'autre
                # L'IA doit fournir l'id à garder et l'id à supprimer dans champs_a_modifier
                id_a_supprimer = modif["champs_a_modifier"].get("supprimer_id")
                if id_a_supprimer:
                    cur.execute(
                        f"DELETE FROM {modif['table']} WHERE id = %s",
                        (id_a_supprimer,)
                    )

    conn.commit()

def generation_par_sections():
    sections_json = recup_sections()  # string JSON
    sections_data = json.loads(sections_json)  # redevient un dict Python
    sections = sections_data["sections"] # récupère la liste

    sections_triees = sorted(sections, key=lambda x: (x["chapitre_id"], x["ordre"]))

    for fichier in sections_triees:
        with conn.cursor() as cur:
            print(fichier)
            generation_section(fichier["ordre"], fichier["chapitre_id"], fichier["id"], fichier["chapitre_id"])

def generation_section(numero_section, numero_chapitre, section_id, chapitre_id):
    file = open("prompt_test/ecriture_section.txt", 'r', encoding="utf-8")
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
    ajout_contenu_section_bdd(section_id, chapitre_id, json.loads(response.message.content)["contenu"])
    infos_json = extraire_infos_section(response.message.content,numero_chapitre,numero_section)
    ajout_bdd_infos(infos_json)
    return json.loads(response.message.content)

def extraire_infos_section(texte_section, numero_chapitre, numero_section):
    file = open("prompt_test/remplissage_infos.txt", 'r', encoding="utf-8")
    prompt = file.read()
    fichiers_a_recup = ["infos"]
    data_needed = recup_fichiers(fichiers_a_recup)
    infos: str = ""
    for data in data_needed:
        infos = infos + data

    print("Remplissage infos section", numero_section, "du chapitre", numero_chapitre, "en cours")
    response = chat(
        model=model,
        messages=[{'role': 'user', 'content': (
                "{infos}" + infos + "{/infos}"
                "{numero_section}" + str(numero_section) + "{/numero_section}" +
                "{numero_chapitre}" + str(
            numero_chapitre) + "{/numero_chapitre}" + "{contexte}" + texte_section + "{/contexte}" + prompt)}], )

    file.close()
    print(response.message.content)
    return json.loads(response.message.content)

def reset_glossaire():
    with conn.cursor() as cur:
        cur.execute("""
                            TRUNCATE glossaire RESTART IDENTITY CASCADE;
                        """)
        conn.commit()
        print("Reset glossaire effectué")

def reset_exemples():
    with conn.cursor() as cur:
        cur.execute("""
                            TRUNCATE exemples RESTART IDENTITY CASCADE;
                        """)
        conn.commit()
        print("Reset exemples effectué")

def reset_affirmations():
    with conn.cursor() as cur:
        cur.execute("""
                            TRUNCATE affirmations_posées RESTART IDENTITY CASCADE;
                        """)
        conn.commit()
        print("Reset affirmations effectué")

def reset_infos():
    reset_glossaire()
    reset_exemples()
    reset_affirmations()
    print("Reset infos effectué")

def ajout_bdd_infos(infos_json):
    print(infos_json)
    with conn.cursor() as cur:
        for info in infos_json["actions"]:
            if info["action"] == "ajouter":
                if info["table"] == "glossaire":
                    cur.execute("""
                    Insert into glossaire (terme, définition_utilisée_dans_ce_livre, mise_en_garde_sur_ce_terme ) values (%s, %s, %s);
                    """,
                    (info["données"]["terme"],info["données"]["définition_utilisée_dans_ce_livre"],info["données"]["mise_en_garde_sur_ce_terme"])
                )
                if info["table"] == "exemples":
                    cur.execute("""
                    Insert into exemples (titre_de_l_exemple, description_complète_de_l_exemple, chiffres_ou_données_utilisés, source_ou_origine) values (%s, %s, %s, %s);
                    """,
                                (info["données"]["titre_de_l_exemple"],info["données"]["description_complète_de_l_exemple"],info["données"]["chiffres_ou_données_utilisés"], info["données"]["source_ou_origine"])
                                )
                if info["table"] == "affirmations_posées":
                    cur.execute("""
                    Insert into affirmations_posées (contenu_de_l_affirmation, type_affirmation, à_ne_pas_contredire) values (%s,%s,%s);
                    """,
                                (info["données"]["contenu_de_l_affirmation"],info["données"]["type_affirmation"],info["données"]["à_ne_pas_contredire"])
                    )
            if info["action"] == "modifier":
                if info["table"] == "glossaire":
                    cur.execute("""
                    Update glossaire set terme = %s, définition_utilisée_dans_ce_livre = %s, mise_en_garde_sur_ce_terme = %s where id = %s;
                    """,
                    (info["données"]["terme"],info["données"]["définition_utilisée_dans_ce_livre"],info["données"]["mise_en_garde_sur_ce_terme"], info["id"])
                )
                if info["table"] == "exemples":
                    cur.execute("""
                    Update exemples set titre_de_l_exemple = %s , description_complète_de_l_exemple = %s, chiffres_ou_données_utilisés = %s, source_ou_origine = %s where id = %s;
                    """,
                                (info["données"]["titre_de_l_exemple"],info["données"]["description_complète_de_l_exemple"],info["données"]["chiffres_ou_données_utilisés"], info["données"]["source_ou_origine"], info["id"])
                                )
                if info["table"] == "affirmations_posées":
                    cur.execute("""
                    Update affirmations_posées set contenu_de_l_affirmation = %s, type_affirmation = %s, à_ne_pas_contredire = %s where id = %s;
                    """,
                                (info["données"]["contenu_de_l_affirmation"],info["données"]["type_affirmation"],info["données"]["à_ne_pas_contredire"], info["id"])
                    )
    conn.commit()

def ajout_contenu_section_bdd(section_id, chapitre_id, contenu_section_json):
    print(contenu_section_json)
    with conn.cursor() as cur:
        cur.execute("""
        Insert into contenu_sections (section_id, chapitre_id, contenu) values (%s, %s, %s); 
        """,
        (section_id, chapitre_id,contenu_section_json)
        )
    conn.commit()

def process():
    flag = True
    while flag :
        print("Reset fiche strat ? (y ou n)")
        reponse = input("Entrez une valeur : ")
        if reponse == "y":
            reset_fiche_strat()
            sujet_brut = input("Donnez le sujet brut : ")
            if sujet_brut != "" and sujet_brut != NULL:
                print("Sujet reçu, création de la fiche stratégique en cours")
                fiche_strat = transformation_sujet_en_fiche_strat(sujet_brut)
                if verif_humaine(fiche_strat):
                    ajout_bdd_fiche_strat(fiche_strat)

        print("Restart recherches (y ou n)")
        rep = input("Entrez une valeur : ")
        if rep == "y":
            reset_recherches()
            recherches_ia_et_ajout_bdd()
        print("Restart plan (y ou n)")
        rep = input("Entrez une valeur : ")
        if rep == "y":
            reset_plan()
            ajout_bdd_plan(creation_plan())
        print("Cadrage ? (y ou n)")
        rep = input("Entrez une valeur : ")
        if rep == "y":
            cadrage_mots_par_sections(demande_cadrage_mots_par_sections())
        print("Verification ? (y ou n)")
        rep = input("Entrez une valeur : ")
        if rep == "y":
            modifications_a_effectuer = verifcation_plan()
            print("Effectuer les modifications ? (y ou n)")
            rep = input("Entrez une valeur : ")
            if rep == "y" :
                modif_post_verif_plan(modifications_a_effectuer)
                print("Modifications faites")
            else :
                print("Recommencer le plan ? (y ou n)")
        flag = False

def menu():
    print("De où faut-il partir ?")
    print("0. Nettoyer la base de données")
    print("1. Fiche stratégique")
    print("2. Recherches")
    print("3. Plan")
    print("4. Cadrage")
    print("5. Vérifications")
    print("6. Générations")
    rep = input("Entrez une valeur : ")
    if rep == "0":
        menu_nettoyage_bdd()
        return
    elif rep == "1":
        process_v2("fiche_strategique")
        return
    elif rep == "2":
        process_v2("recherches")
        return
    elif rep == "3":
        process_v2("plan")
        return
    elif rep == "4":
        process_v2("cadrage")
        return
    elif rep == "5":
        process_v2("verifications")
        return
    elif rep == "6":
        process_v2("generations")
    else:
        menu()
        return

def menu_nettoyage_bdd():
    print("Que faut-il nettoyer ?")
    print("0. Tout")
    print("1. Fiche stratégique")
    print("2. Recherches")
    print("3. Plan")
    print("4. Infos")
    print("5. Contenu sections")
    print("6. Retourner au menu principal")

    rep_1 = input("Entrez une valeur : ")
    if rep_1 == "0":
        reset_fiche_strat()
        reset_recherches()
        reset_plan()
        reset_infos()
        reset_contenu_sections()
        menu()
        return
    elif rep_1 == "1":
        reset_fiche_strat()
    elif rep_1 == "2":
        reset_fiche_strat()
    elif rep_1 == "3":
        reset_fiche_strat()
    elif rep_1 == "4":
        reset_infos()
    elif rep_1 == "5":
        reset_contenu_sections()
    elif rep_1 == "6":
        menu()
        return
    menu_nettoyage_bdd()
    return

def process_v2(etat):
    match etat:
        case "spawn" :
            menu()
        case "fiche_strategique":
            reset_fiche_strat()
            sujet_brut = input("Donnez le sujet brut : ")
            if sujet_brut != "" and sujet_brut != NULL:
                print("Sujet reçu, création de la fiche stratégique en cours")
                fiche_strat = transformation_sujet_en_fiche_strat(sujet_brut)
                if verif_humaine(fiche_strat):
                    ajout_bdd_fiche_strat(fiche_strat)
                    process_v2("recherches")
                    return
                else :
                    print("Recommencer le plan ? (y ou n)")
                    rep = input("Entrez une valeur : ")
                    if rep == "y" :
                        process_v2("fiche_strategique")
                        return
                    else:
                        menu()
                        return
        case "recherches":
            print("Recherches :")
            reset_recherches()
            recherches_ia_et_ajout_bdd()
            process_v2("plan")
            return
        case "plan":
            print("Création du plan...")
            reset_plan()
            ajout_bdd_plan(creation_plan())
            process_v2("cadrage")
            return
        case "cadrage":
            print("Cadrage...")
            cadrage_mots_par_sections(demande_cadrage_mots_par_sections())
            process_v2("verifications")
        case "verifications":
            print("Verifications...")
            modifications_a_effectuer = verifcation_plan()
            process_v2("modifications_a_effectuer")
            print("Acceptez-vous les modifications ? (y ou n)")
            rep = input("Entrez une valeur : ")
            if rep == "y" :
                modif_post_verif_plan(modifications_a_effectuer)
                process_v2("generations")
            else:
                print("Recommencer le plan ? (y ou n)")
                rep = input("Entrez une valeur : ")
                if rep == "y" :
                    process_v2("plan")
                    return
                else:
                    menu()
                    return
        case "generations":
            generation_par_sections()


process_v2("spawn")