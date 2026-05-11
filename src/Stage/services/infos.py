import json
from ollama import chat

from .normalisation import safe_json
from ..models import Glossaire, Exemple,Affirmation, ProcessStatus
import os
from .json_cleaner import PLAN_VERIF_SCHEMA, INFOS_SCHEMA, clean_json, filtrer_champs_valides

from ..settings import BASE_DIR


def recup_glossaire():
    glossaire = list(Glossaire.objects.values(
        "id", "terme", "définition_utilisée_dans_ce_livre", "mise_en_garde_sur_ce_terme"
    ))
    return json.dumps({"glossaire": glossaire}, ensure_ascii=False, indent=2)


def recup_exemples():
    exemples = list(Exemple.objects.values(
        "id", "titre_de_l_exemple", "description_complète_de_l_exemple",
        "chiffres_ou_données_utilisés", "source_ou_origine"
    ))
    return json.dumps({"exemples": exemples}, ensure_ascii=False, indent=2)


def recup_affirmations():
    affirmations = list(Affirmation.objects.values(
        "id", "contenu_de_l_affirmation", "type_affirmation", "à_ne_pas_contredire"
    ))
    return json.dumps({"affirmations_posées": affirmations}, ensure_ascii=False, indent=2)

def recup_infos():
    infos : list = []
    infos.append(recup_glossaire())
    infos.append(recup_exemples())
    infos.append(recup_affirmations())
    return infos

def ajout_bdd_infos(infos_json):
    print(infos_json)

    infos_json = filtrer_champs_valides(infos_json, INFOS_SCHEMA)

    TABLE_MAP = {
        "glossaire": Glossaire,
        "exemples": Exemple,
        "affirmations_posées": Affirmation,
    }

    for info in infos_json["actions"]:
        model_class = TABLE_MAP[info["table"]]
        données = info["données"]

        if info["action"] == "ajouter":
            model_class.objects.create(**données)

        elif info["action"] == "modifier":
            model_class.objects.filter(id=info["id"]).update(**données)

def reset_glossaire():
    Glossaire.objects.all().delete()
    print("Reset glossaire effectué")

def reset_exemples():
    Exemple.objects.all().delete()
    print("Reset exemples effectué")

def reset_affirmations():
    Affirmation.objects.all().delete()
    print("Reset affirmations effectué")

def reset_infos():
    reset_glossaire()
    reset_exemples()
    reset_affirmations()
    print("Reset infos effectué")

def extraire_infos_section(texte_section, numero_chapitre, numero_section):
    from .fonctions_globales import model, recup_fichiers

    status, _ = ProcessStatus.objects.get_or_create(id=1)

    prompt = os.path.join(BASE_DIR, 'Stage/prompts/remplissage_infos.txt')
    file = open(prompt, 'r', encoding="utf-8")
    prompt = file.read()
    fichiers_a_recup = ["infos"]
    data_needed = recup_fichiers(fichiers_a_recup)
    infos: str = ""
    for data in data_needed:
        infos = infos + data

    infos_str = json.dumps(infos, ensure_ascii=False)
    texte_section_str = json.dumps(texte_section, ensure_ascii=False)
    numero_section_str = json.dumps(numero_section, ensure_ascii=False)
    numero_chapitre_str = json.dumps(numero_chapitre, ensure_ascii=False)
    print("Remplissage infos section", numero_section, "du chapitre", numero_chapitre, "en cours")

    status.message = f"Extractions des infos de la section {numero_section} du chapitre {numero_chapitre} ..."
    status.save()

    response = chat(
        model=model,
        messages=[{'role': 'user', 'content': (
                "{infos}" + infos_str + "{/infos}"
                "{numero_section}" + numero_section_str + "{/numero_section}" +
                "{numero_chapitre}" + numero_chapitre_str + "{/numero_chapitre}" + "{contexte}" + texte_section_str + "{/contexte}" + prompt)}], )

    file.close()
    print(response.message.content)
    return json.loads(response.message.content)


