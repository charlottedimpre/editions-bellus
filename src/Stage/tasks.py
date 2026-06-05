from celery import shared_task



from .models import ProcessStatus



from celery.signals import worker_ready

from .fonctions.fiche_cadrage import fc
from .fonctions.web_search.web_search import webinput, websearch, webfetch, weboutput
from .fonctions.plan_detaille import plan_detail
from .fonctions.structure_chapitre import structure_chapitre
from .fonctions.introduction import gen_intro
from .fonctions.sections.section import suivisection, reprise_generation
from .fonctions.conclusion import gen_conclu
from .fonctions.fil_rouge.fil_rouge import gen_filrouge_with_validation, merge_filrouge_wrapper
from .fonctions.prepostface.preface import gen_preface
from .fonctions.prepostface.postface import gen_postface

@worker_ready.connect
def celery_ready(sender, **kwargs):
    from django.utils.timezone import now

    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = f"Celery prêt ✅ ({now()})"
    status.progress = 0
    status.sujet_precis = ""
    status.is_done = False
    status.save()


from celery.signals import worker_shutdown

@worker_shutdown.connect
def celery_shutdown(sender, **kwargs):
    from django.utils.timezone import now
    from .models import ProcessStatus

    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = f"⚠️ Celery arrêté ({now()})"
    status.save()

from celery.signals import task_failure

@task_failure.connect
def on_task_failure(sender, task_id, exception, traceback, eargs, kwargs, **kw):
    from .models import ProcessStatus

    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = f"❌ Erreur : {exception}"
    status.save()


@shared_task
def fiche_cadrage_task(sujet, livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.progress = 0
    status.message = "Création de la fiche cadrage en cours..."
    status.is_done = False
    status.save()

    f_c = fc(sujet, "1", livre_id)
    status.sujet_precis = f_c

    status.progress = 100
    status.message = "Ecriture de la fiche cadrage terminée..."
    status.is_done = True
    status.redirect_url = "/" + str(livre_id) + "/fiche-cadrage/"
    status.save()

@shared_task
def websearch_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Generation des requetes..."
    status.progress = 0
    status.save()
    queries_payload = webinput(livre_id)

    status.message = "Recherche web (API SERP)..."
    status.progress = 25
    status.save()
    search_results = websearch(queries_payload)

    status.message = "Recuperation des contenus..."
    status.progress = 50
    status.save()
    content_data = webfetch(search_results)

    status.message = "Synthese finale..."
    status.progress = 75
    status.save()
    weboutput(livre_id, content_data)

    status.message = "Recherches web terminees."
    status.progress = 100
    status.save()

@shared_task
def plan_details_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = "Création d'un plan détaillé en cours..."
    status.progress = 0
    status.save()

    plan_detail(livre_id)

    status.message = "Création d'un plan détaillé terminée"
    status.progress = 100
    status.save()

@shared_task
def structure_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = "Création de la structure du livre en cours..."
    status.progress = 0
    status.save()

    structure_chapitre(livre_id)

    status.message = "Création de la structure du livre terminée"
    status.progress = 100
    status.save()
@shared_task
def introduction_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération de l'introduction en cours..."
    status.progress = 0
    status.save()

    gen_intro(livre_id)

    status.message = "Génération de l'introduction terminée"
    status.progress = 100
    status.save()


@shared_task
def preface_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération de la préface en cours..."
    status.progress = 0
    status.save()

    gen_preface(livre_id)

    status.message = "Génération de la préface terminée"
    status.progress = 100
    status.save()

@shared_task
def generation_section_task(livre_id, reprise=False):
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    try :
        status.message = "Génération des sections en cours..."
        status.progress = 0
        status.save()

        if reprise:
            reprise_generation(livre_id)
        else:
            suivisection(livre_id)

        status.message = "Génération des sections terminée"
        status.progress = 50
        status.save()

        status.message = "Génération du fil rouge en cours..."
        status.progress = 50
        status.save()
        gen_filrouge_with_validation(livre_id)

        status.message = "Merge du fil rouge en cours..."
        status.progress = 75
        status.save()

        merge_filrouge_wrapper(livre_id)

        status.message = "Génération sections terminées"
        status.progress = 100
        status.save()

    except Exception as e:
        status.message = f"❌ Erreur : {e}"
        status.progress = 0
        status.save()
        raise
@shared_task
def conclusion_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération de la conclusion en cours..."
    status.progress = 0
    status.save()

    gen_conclu(livre_id)

    status.message = "Génération de la conclusion terminée"
    status.progress = 100
    status.save()


@shared_task
def postface_task(livre_id):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Génération de la postface en cours..."
    status.progress = 0
    status.save()

    gen_postface(livre_id)

    status.message = "Génération de la postface terminée"
    status.progress = 100
    status.save()


@shared_task
def export_task(livre_id, format: str):
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.message = f"Export {format.upper()} en cours..."
    status.progress = 0
    status.is_done = False
    status.save()

    try:
        if format == "pdf":
            from .fonctions.export.affichage_pdf import affichage_pdf
            affichage_pdf(livre_id)
        elif format == "docx":
            from .fonctions.export.affichage_doc import affichage_doc
            affichage_doc(livre_id)
        elif format == "md":
            from .fonctions.export.affichage_md import affichage_md
            affichage_md(livre_id)
        else:
            raise ValueError(f"Format inconnu : {format}")

        status.message = f"Export {format.upper()} terminé."
        status.progress = 100
        status.is_done = True
        status.save()

    except Exception as e:
        status.message = f"Erreur export {format.upper()} : {e}"
        status.progress = 0
        status.is_done = True
        status.save()
        raise

