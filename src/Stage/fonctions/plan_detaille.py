import json
from pathlib import Path
import os
from ollama import ChatResponse, chat

from Stage.fonctions.fiche_cadrage import recup_fiche_cadrage
from Stage.fonctions.web_search.weboutput import recup_web_search
from .parser import parse_plan_detaille

from ..settings import BASE_DIR

from ..models import Introduction, Conclusion,FilRouge,ChapitreDetails


def _normalize_ws_final(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"sources_web": payload}
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {"sources_web": []}
        try:
            parsed = json.loads(text)
            return _normalize_ws_final(parsed)
        except json.JSONDecodeError:
            return {"sources_web_raw": text}
    return {"sources_web_raw": str(payload)}


def sources() -> dict:
    payload = recup_web_search()
    return _normalize_ws_final(payload)


def plan_detail():

    #Pour le prompt
    prompt = os.path.join(BASE_DIR, 'Stage/input/pd_prompt.txt')
    file = open(prompt, 'r')
    prompt_recherche = file.read()

    fiche_cadrage = recup_fiche_cadrage()

    #Récupérer les recherches
    sources_web = json.dumps(sources(), ensure_ascii=False, indent=2)

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': (
                f'{prompt_recherche}\n\n'
                f'FICHE DE CADRAGE : {fiche_cadrage}\n\n'
                f'SOURCES WEB (JSON) : {sources_web}'
            ),
        },
    ])
    parsed = parse_plan_detaille(response.message.content)

    ajout_plan_detail_bdd(parsed)


if __name__ == '__main__':
    plan_detail()


def ajout_plan_detail_bdd(data):
    # 🔹 Introduction
    intro_data = data.get("introduction", {})
    Introduction.objects.create(
        contexte=intro_data.get("contexte"),
        importance=intro_data.get("importance"),
        adresse_a=intro_data.get("adresse_a"),
        organisation=intro_data.get("organisation"),
        promesse=intro_data.get("promesse"),
    )

    # 🔹 Conclusion
    conclusion_data = data.get("conclusion", {})
    Conclusion.objects.create(
        synthese=conclusion_data.get("synthese"),
        logique_ensemble=conclusion_data.get("logique_ensemble"),
        prochaines_etapes=conclusion_data.get("prochaines_etapes"),
    )

    # 🔹 Fil rouge
    fil_rouge_data = data.get("exemple_fil_rouge", {})
    FilRouge.objects.create(
        personnage=fil_rouge_data.get("personnage"),
        situation_depart=fil_rouge_data.get("situation_depart"),
        evolution=fil_rouge_data.get("evolution"),
    )

    # 🔹 Chapitres
    for chapitre_data in data.get("chapitres", []):
        ChapitreDetails.objects.create(
            numero=chapitre_data.get("numero"),
            titre=chapitre_data.get("titre"),
            traite=chapitre_data.get("traite"),
            ne_traite_pas=chapitre_data.get("ne_traite_pas"),
            pourquoi_distinct=chapitre_data.get("pourquoi_distinct"),
        )

    print("Données insérées avec succès.")

def recup_plan_detail():
        intro = Introduction.objects.last()
        conclusion = Conclusion.objects.last()
        fil_rouge = FilRouge.objects.last()
        chapitres = ChapitreDetails.objects.all().order_by("numero")

        return json.dumps({
            "introduction": {
                "contexte": intro.contexte if intro else None,
                "importance": intro.importance if intro else None,
                "adresse_a": intro.adresse_a if intro else None,
                "organisation": intro.organisation if intro else None,
                "promesse": intro.promesse if intro else None,
            },
            "chapitres": [
                {
                    "numero": chap.numero,
                    "titre": chap.titre,
                    "traite": chap.traite,
                    "ne_traite_pas": chap.ne_traite_pas,
                    "pourquoi_distinct": chap.pourquoi_distinct,
                }
                for chap in chapitres
            ],
            "conclusion": {
                "synthese": conclusion.synthese if conclusion else None,
                "logique_ensemble": conclusion.logique_ensemble if conclusion else None,
                "prochaines_etapes": conclusion.prochaines_etapes if conclusion else None,
            },
            "exemple_fil_rouge": {
                "personnage": fil_rouge.personnage if fil_rouge else None,
                "situation_depart": fil_rouge.situation_depart if fil_rouge else None,
                "evolution": fil_rouge.evolution if fil_rouge else None,
            }
        }, ensure_ascii=False, indent=2)

def reset_plan_detail():
    Introduction.objects.all().delete()
    Conclusion.objects.all().delete()
    FilRouge.objects.all().delete()
    ChapitreDetails.objects.all().delete()