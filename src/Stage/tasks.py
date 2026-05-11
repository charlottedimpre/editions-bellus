from celery import shared_task
from django.shortcuts import redirect

from .fonctions.export.affichage import affichage
from .models import ProcessStatus
import json


from celery.signals import worker_ready

from .fonctions.fiche_cadrage import fiche_cadrage, ajout_bdd_fiche_cadrage, recup_fiche_cadrage, fc
from .fonctions.web_search.webinput import webinput_wrapper
from .fonctions.web_search.web import web_search_wrapper
from .fonctions.web_search.webfetch import webfetch_wrapper
from .fonctions.web_search.weboutput import weboutput_wrapper
from .fonctions.plan_detaille import plan_detail
from .fonctions.structure_chapitre import structure_chapitre
from .fonctions.introduction import gen_intro
from .fonctions.sections.section import suivisection, reset_all_test
from .fonctions.conclusion import gen_conclu
from .fonctions.export.affichage import affichage

@worker_ready.connect
def celery_ready(sender, **kwargs):
    from django.utils.timezone import now

    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = f"Celery prêt ✅ ({now()})"
    status.progress = 0
    status.sujet_precis = ""
    status.save()



@shared_task
def fiche_cadrage_task(sujet):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.progress = 0
    status.message = "Création de la fiche cadrage en cours..."
    status.is_done = False
    status.save()

    f_c = fc(sujet, "1")
    status.sujet_precis = f_c

    status.progress = 100
    status.message = "Ecriture de la fiche cadrage terminée..."
    status.is_done = True
    status.redirect_url = "/fiche-cadrage/"
    status.save()

@shared_task
def websearch_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = "Recherches webs en cours..."
    status.save()

    status.message = "Web input en cours..."
    status.progress = 0
    status.save()
    webinput_wrapper()

    status.message = "Web search en cours..."
    status.progress = 25
    status.save()
    web_search_wrapper()

    status.message = "Web fetch en cours..."
    status.progress = 50
    status.save()
    webfetch_wrapper()

    status.message = "Web output en cours..."
    status.progress = 75
    status.save()
    weboutput_wrapper()

    status.message = "Recherches web terminées..."
    status.progress = 100
    status.save()

@shared_task
def plan_details_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = "Création d'un plan détaillé en cours..."
    status.progress = 0
    status.save()

    plan_detail()

    status.message = "Création d'un plan détaillé terminée"
    status.progress = 100
    status.save()

@shared_task
def structure_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = "Création de la structure du livre en cours..."
    status.progress = 0
    status.save()

    structure_chapitre()

    status.message = "Création de la structure du livre terminée"
    status.progress = 100
    status.save()
@shared_task
def introduction_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération de l'introduction en cours..."
    status.progress = 0
    status.save()

    gen_intro()

    status.message = "Génération de l'introduction terminée"
    status.progress = 100
    status.save()

@shared_task
def generation_section_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération des sections en cours..."
    status.progress = 0
    status.save()

    suivisection()

    status.message = "Génération des sections terminée"
    status.progress = 100
    status.save()

@shared_task
def conclusion_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération de la conclusion en cours..."
    status.progress = 0
    status.save()

    gen_conclu()

    status.message = "Génération de la conclusion terminée"
    status.progress = 100
    status.save()

@shared_task
def export_pdf_task():
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = "Export en cours..."
    status.progress = 0
    status.save()

    affichage()

    status.message = "Export terminé..."
    status.progress = 100
    status.save()

