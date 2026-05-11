from django.http import JsonResponse
from django.shortcuts import render
from django.http import FileResponse, Http404

from .services.recherches import *
from .services.process import *

from .tasks import *
import docker

from .fonctions.fiche_cadrage import reset_fiche_cadrage
from .fonctions.sections.section import recup_section_texte_all
from .fonctions.web_search.weboutput import recup_web_search, reset_web_search
from .fonctions.plan_detaille import recup_plan_detail, reset_plan_detail
from .fonctions.structure_chapitre import recup_chapitres_sections, reset_structure
from .fonctions.introduction import recup_intro, reset_intro
from .fonctions.conclusion import recup_conclusion, reset_conclusion



def test(request):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    status.message = "Redémarrage Celery..."
    status.save()

    client = docker.from_env()
    container = client.containers.get("busy_greider")

    container.restart()

    # 🔥 attendre que Celery soit VRAIMENT prêt
    if wait_for_celery(container):
        status.message = "Celery prêt ✅"
    else:
        status.message = "Erreur démarrage ❌"

    status.save()
def index(request):

    return render(request, "index.html", context={"prenom" : "Antoine"})

def menu(request):
    return render(request, "menu.html")

def process(request):
    pass

def process_view(request):
    return render(request, "process.html")

def progress_view(request):
    status = ProcessStatus.objects.first()

    if not status:
        return JsonResponse({
            "progress": 0,
            "message": "En attente...",
            "is_done": False,
            "redirect_url": ""
        })

    return JsonResponse({
        "progress": status.progress,
        "message": status.message,
        "is_done": status.is_done,
        "redirect_url": status.redirect_url
    })




def menu_reset(request):
    return render(request, "menu-reset-bdd.html")



def menu_affichage(request):
    return render(request, "menu-affichage.html")

#Affichage New Pages
def affichage_fiche_cadrage(request):
    fiche_obj = FicheCadrage.objects.last()

    # 🔥 Gestion du POST (sauvegarde)
    if request.method == "POST":
        if fiche_obj:
            fiche_obj.sujet = request.POST.get("sujet")
            fiche_obj.sommaire = request.POST.get("sommaire")
            fiche_obj.hors_perimetre = request.POST.get("hors_perimetre")
            fiche_obj.cible = request.POST.get("cible")
            fiche_obj.niveau = request.POST.get("niveau")
            fiche_obj.objectif_lecteur = request.POST.get("objectif_lecteur")
            fiche_obj.nb_chapitre = request.POST.get("nb_chapitre")
            fiche_obj.save()
        else:
            FicheCadrage.objects.create(
                sujet=request.POST.get("sujet"),
                sommaire=request.POST.get("sommaire"),
                hors_perimetre=request.POST.get("hors_perimetre"),
                cible=request.POST.get("cible"),
                niveau=request.POST.get("niveau"),
                objectif_lecteur=request.POST.get("objectif_lecteur"),
                nb_chapitre=request.POST.get("nb_chapitre"),
            )

    # 🔁 On garde TON système JSON
    fiche = recup_fiche_cadrage()

    try:
        fiche = json.loads(fiche)
        fiche_list = fiche.get("fiche_cadrage", [])
        fiche = fiche_list[0] if fiche_list else None
    except Exception:
        fiche = None

    etapes = recup_etapes()
    return render(
        request,
        "affichage/fiche-cadrage.html",
        {
            "fiche": fiche,
            "etapes": etapes,
            "current_step" : 1,
            "prev_step" : "/sujet/",
            "next_step" : "/recherche/",
         "progress_pct" : round(process_percent(etapes))}
    )

def affichage_web_search(request):
    from .models import NotionIndispensable, ErreurFrequente, EtapeEssentielle, Risque
    import json

    # 🔥 SAUVEGARDE
    if request.method == "POST":
        for key, value in request.POST.items():

            if key.startswith("notion_"):
                idx = key.split("_")[1]
                NotionIndispensable.objects.filter(id=idx).update(
                    contenu_de_la_notion=value
                )

            elif key.startswith("erreur_"):
                idx = key.split("_")[1]
                ErreurFrequente.objects.filter(id=idx).update(
                    contenu_de_l_erreur=value
                )

            elif key.startswith("etape_"):
                idx = key.split("_")[1]
                EtapeEssentielle.objects.filter(id=idx).update(
                    contenu_de_l_etapes=value
                )

            elif key.startswith("risque_"):
                idx = key.split("_")[1]
                Risque.objects.filter(id=idx).update(
                    contenu_du_risque=value
                )

    # 🔁 Chargement des données
    data = recup_web_search()
    data = json.loads(data)
    etapes = recup_etapes()
    return render(request, "affichage/websearch.html", context={
        "notions": json.loads(data["notion_indispensables"])["notions_indispensables"],
        "erreurs": json.loads(data["erreurs_frequentes"])["erreurs_frequents"],
        "etapes_es": json.loads(data["etapes_essentielles"])["etapes_essentielles"],
        "risques": json.loads(data["risques"])["risque"], "etapes" : etapes,
        "current_step": 2, "prev_step": "/fiche-cadrage/", "next_step": "/plan/",
        "progress_pct": round(process_percent(etapes))
    })
def affichage_plan_detail(request):
    intro = Introduction.objects.last()
    conclusion = Conclusion.objects.last()
    fil = FilRouge.objects.last()
    chapitres = ChapitreDetails.objects.all().order_by("numero")

    # 🔥 POST = sauvegarde
    if request.method == "POST":

        if intro:
            intro.contexte = request.POST.get("contexte")
            intro.importance = request.POST.get("importance")
            intro.adresse_a = request.POST.get("adresse_a")
            intro.organisation = request.POST.get("organisation")
            intro.promesse = request.POST.get("promesse")
            intro.save()

        if conclusion:
            conclusion.synthese = request.POST.get("synthese")
            conclusion.logique_ensemble = request.POST.get("logique_ensemble")
            conclusion.prochaines_etapes = request.POST.get("prochaines_etapes")
            conclusion.save()

        if fil:
            fil.personnage = request.POST.get("personnage")
            fil.situation_depart = request.POST.get("situation_depart")
            fil.evolution = request.POST.get("evolution")
            fil.save()

        for chap in chapitres:
            chap.traite = request.POST.get(f"traite_{chap.id}")
            chap.ne_traite_pas = request.POST.get(f"ne_traite_pas_{chap.id}")
            chap.pourquoi_distinct = request.POST.get(f"pourquoi_{chap.id}")
            chap.save()

    etapes = recup_etapes()
    return render(request, "affichage/plan_details.html", {
        "introduction": intro,
        "conclusion": conclusion,
        "fil_rouge": fil,
        "chapitres": chapitres, "etapes" : etapes,
        "current_step": 3, "prev_step": "/recherche/", "next_step": "/structure/",
        "progress_pct": round(process_percent(etapes))
    })
def affichage_structure(request):
    chapitres = ChapitreDetails.objects.all().prefetch_related("sections").order_by("numero")

    # 🔥 POST = sauvegarde
    if request.method == "POST":
        for chapitre in chapitres:
            for section in chapitre.sections.all():

                section.objectif = request.POST.get(f"objectif_{section.id}")
                section.concept_cle = request.POST.get(f"concept_{section.id}")
                section.exemple = request.POST.get(f"exemple_{section.id}")
                section.limite = request.POST.get(f"limite_{section.id}")
                section.mots_cible = request.POST.get(f"mots_{section.id}")

                section.save()

    etapes = recup_etapes()
    return render(request, "affichage/structure.html", {
        "chapitres": chapitres, "etapes" : etapes,
        "current_step": 4, "prev_step": "/plan/", "next_step": "/introduction/",
        "progress_pct": round(process_percent(etapes))
    })

def affichage_intro(request):
    intro_obj = IntroductionTexte.objects.last()

    # 🔥 Gestion POST (sauvegarde)
    if request.method == "POST":
        texte = request.POST.get("intro")

        if intro_obj:
            intro_obj.intro = texte
            intro_obj.save()
        else:
            IntroductionTexte.objects.create(
                intro=texte
            )

    # 🔁 récupération JSON (comme ton système actuel)
    try:
        data = json.loads(recup_intro())
        intro = data.get("intro")
    except Exception:
        intro = None

    etapes = recup_etapes()
    return render(request, "affichage/introduction.html", {
        "intro": intro, "etapes" : etapes,
        "current_step": 5, "prev_step": "/structure/", "next_step": "/contenu/",
        "progress_pct": round(process_percent(etapes))
    })
def affichage_sections_texte(request):
    sections = recup_section_texte_all()

    # 🔹 mapping titres
    chapitres_db = {
        c.numero: c.titre
        for c in ChapitreDetails.objects.all()
    }

    sections_db = {
        (s.chapitre.numero, s.numero): s.titre_section
        for s in SectionDetaillee.objects.select_related("chapitre").all()
    }

    # 🔥 UPDATE SECTION
    if request.method == "POST":
        chapitre = request.POST.get("chapitre")
        section = request.POST.get("section")
        contenu = request.POST.get("contenu")

        obj = SectionTexte.objects.filter(
            chapitre=chapitre,
            section=section
        ).first()

        if obj:
            obj.contenu = contenu
            obj.save()

    # 🔹 enrichissement
    for s in sections:
        s["titre_chapitre"] = chapitres_db.get(
            s["chapitre"], f"Chapitre {s['chapitre']}"
        )
        s["titre_section"] = sections_db.get(
            (s["chapitre"], s["section"]),
            f"Section {s['section']}"
        )

    # 🔹 regroupement
    chapitres = {}
    for s in sections:
        chapitres.setdefault(s["chapitre"], []).append(s)

    etapes = recup_etapes()
    return render(request, "affichage/sections_texte.html", {
        "chapitres": chapitres, "etapes" : etapes,
        "current_step": 6, "prev_step": "/introduction/", "next_step": "/conclusion/",
        "progress_pct": round(process_percent(etapes))
    })

def affichage_conclusion(request):
    conclusion_obj = ConclusionTexte.objects.last()

    # 🔥 Gestion POST (sauvegarde)
    if request.method == "POST":
        texte = request.POST.get("conclusion")

        if conclusion_obj:
            conclusion_obj.conclusion = texte
            conclusion_obj.save()
        else:
            ConclusionTexte.objects.create(
                conclusion=texte
            )

    # 🔁 récupération JSON (comme ton système)
    try:
        data = json.loads(recup_conclusion())
        conclusion = data.get("conclusion")
    except Exception:
        conclusion = None

    etapes = recup_etapes()
    return render(request, "affichage/conclusion.html", {
        "conclusion": conclusion, "etapes" : etapes,
        "current_step": 7, "prev_step": "/contenu/", "next_step": "/export/",
        "progress_pct": round(process_percent(etapes))
    })

def fiche_cadrage_task_view(request):
    status, _ = ProcessStatus.objects.get_or_create(id=1)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "valider":
            status, _ = ProcessStatus.objects.get_or_create(id=1)

            fiche_c = status.sujet_precis
            ajout_bdd_fiche_cadrage(fiche_c, True)

            # reset
            status.sujet_precis = ""
            status.save()

            return redirect('menu')

        else:
            sujet = request.POST["sujet"]
            fiche_cadrage_task.delay(sujet)
            etapes = recup_etapes()
            return render(request, "fiche-cadrage.html", {"sujet": sujet,"etapes" : etapes,
                                                                                "current_step": 0, "next_step": "/fiche-cadrage/",
                                                                                "progress_pct": round(process_percent(etapes))})

    if status.sujet_precis:
        sujet_precis = status.sujet_precis

        status.is_done = False
        status.save()

        return render(request, "fiche-cadrage.html", {
            "sujet_precis": sujet_precis
        })
    etapes = recup_etapes()
    return render(request, "fiche-cadrage.html",
                  {"etapes": etapes,
                            "current_step": 0, "next_step": "/fiche-cadrage/",
                            "progress_pct": round(process_percent(etapes))
                            })

def websearch_task_view(request):
    websearch_task.delay()
    return JsonResponse({"status": "ok"})

def plan_detail_task_view(request):
    plan_details_task.delay()
    return JsonResponse({"status": "ok"})

def structure_task_view(request):
    structure_task.delay()
    return JsonResponse({"status": "ok"})

def introduction_task_view(request):
    introduction_task.delay()
    return JsonResponse({"status": "ok"})

def gen_section_task_view(request):
    generation_section_task.delay()
    return JsonResponse({"status": "ok"})


def conclusion_task_view(request):
    conclusion_task.delay()
    return JsonResponse({"status": "ok"})

def reset_fiche_cadrage_view(request):
    if request.method == "POST":
        reset_fiche_cadrage()
        return JsonResponse({"status": "ok", "message": "Fiche cadrage réinitialisée"})

def reset_web_search_view(request):
    if request.method == "POST":
        reset_web_search()
        return JsonResponse({"status": "ok", "message": "Recherches web réinitialisés"})

def reset_plan_detail_view(request):
    if request.method == "POST":
        reset_plan_detail()
        return JsonResponse({"status": "ok", "message": "Plan détaillé réinitialisé"})

def reset_structure_view(request):
    if request.method == "POST":
        reset_structure()
        return JsonResponse({"status": "ok", "message": "Structure réinitialisée"})

def reset_introduction_view(request):
    if request.method == "POST":
        reset_intro()
        return JsonResponse({"status": "ok", "message": "Introduction réinitialisée"})

def reset_section_texte_view(request):
    if request.method == "POST":
        reset_all_test()
        return JsonResponse({"status": "ok", "message": "Reset Section texte"})

def reset_conclusion_view(request):
    if request.method == "POST":
        reset_conclusion()
        return JsonResponse({"status": "ok", "message": "Conclusion réinitialisée"})

def reset_all_post_merge_view(request):
    if request.method == "POST":
        reset_fiche_cadrage()
        reset_web_search()
        reset_plan_detail_view()
        reset_structure_view()
        reset_introduction_view()
        reset_section_texte_view()
        reset_conclusion_view()
        return JsonResponse({"status": "ok", "message": "Tout réinitialisé"})

def export_pdf_task_view(request):
    export_pdf_task.delay()
    return JsonResponse({"status": "ok"})



PDF_DIR = os.path.join(BASE_DIR, "Stage/fonctions/export/output")

def liste_pdfs(request):
    try:
        fichiers = [
            f for f in os.listdir(PDF_DIR)
            if f.endswith(".pdf")
        ]
    except FileNotFoundError:
        fichiers = []

    return render(request, "affichage/liste_pdfs.html", {
        "fichiers": fichiers
    })


def telecharger_pdf(request, nom_fichier):
    chemin = os.path.join(PDF_DIR, nom_fichier)

    # 🔒 sécurité (évite ../)
    if not os.path.abspath(chemin).startswith(os.path.abspath(PDF_DIR)):
        raise Http404()

    if not os.path.exists(chemin):
        raise Http404()

    return FileResponse(open(chemin, "rb"), as_attachment=True)

def variables_affichage(request):
    variables = Variables.objects.last()

    # 🔥 POST = sauvegarde
    if request.method == "POST":
        nb_chapitre = request.POST.get("nb_chapitre")
        nb_mots_cible = request.POST.get("nb_mots_cible")

        if variables:
            variables.nb_chapitre = nb_chapitre or None
            variables.nb_mots_cible = nb_mots_cible or None
            variables.save()
        else:
            Variables.objects.create(
                nb_chapitre=nb_chapitre or None,
                nb_mots_cible=nb_mots_cible or None,
            )

    # 🔁 reload après save
    variables = Variables.objects.last()

    return render(request, "affichage/variables.html", {
        "nb_chapitre": variables.nb_chapitre if variables else None,
        "nb_mots_cible": variables.nb_mots_cible if variables else None,
    })

def done_fc():
    fiche_c = Etapes.objects.first()
    fiche_c.fiche_cadrage = True
    fiche_c.save()

def recup_etapes():
    etape = Etapes.objects.first()
    steps = [
        {"num": 0, "label": "Sujet", "done": etape.sujet, "link": "/sujet/"},
        {"num": 1, "label": "Fiche cadrage", "done": etape.fiche_cadrage, "link": "/fiche-cadrage/"},
        {"num": 2, "label": "Recherche", "done": etape.recherche, "link": "/recherche/"},
        {"num": 3, "label": "Plan", "done": etape.plan, "link": "/plan/"},
        {"num": 4, "label": "Structure", "done": etape.structure, "link": "/structure/"},
        {"num": 5, "label": "Introduction", "done": etape.introduction, "link": "/introduction/"},
        {"num": 6, "label": "Contenu", "done": etape.contenu, "link": "/contenu/"},
        {"num": 7, "label": "Conclusion", "done": etape.conclusion, "link": "/conclusion/"},
        {"num": 8, "label": "Export", "link": "/export/"},
    ]
    return steps

def process_percent(etapes):
    count = 0
    for etape in etapes:
        if etape.get("done"):
            count += 1
    return round(count / 7 * 100)