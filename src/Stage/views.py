import docker

import os

from .fonctions.prepostface.postface import reset_postface
from .fonctions.prepostface.preface import reset_preface
from .settings import BASE_DIR
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.http import FileResponse, Http404

from .models import *
from .tasks import *

import json
from .fonctions.fiche_cadrage import reset_fiche_cadrage
from .fonctions.sections.section import recup_section_texte_all, reset_all_test
from .fonctions.web_search.web_search import recup_web_search, reset_web_search
from .fonctions.plan_detaille import reset_plan_detail, recup_plan_detail
from .fonctions.structure_chapitre import reset_structure
from .fonctions.introduction import recup_intro, reset_intro
from .fonctions.conclusion import recup_conclusion, reset_conclusion

import mimetypes
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_POST

from .tasks import export_task
from .fonctions.export.affichage_bdd import OUTPUT_DIR

def livres(request):
    if request.method == "POST":
        if request.POST.get("action") == "supprimer":
            supprimer_livre(request.POST.get("livre_id"))
        else :
            livre_titre = request.POST.get("livre_titre")
            dernier = Livre.objects.order_by("livre_id").last()
            prochain_id = (dernier.livre_id + 1) if dernier and dernier.livre_id else 1
            Livre.objects.create(livre_id=prochain_id, livre_titre=livre_titre)
            Etapes.objects.create(livre_id=prochain_id)
        return redirect(request.path)

    list_livres = Livre.objects.all()
    return render(request, "menu-livres.html", {"livres": list_livres})

def recup_livres():
    list_livres = Livre.objects.all()
    return list_livres


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

def menu_redirect(request):
    return redirect('/livres/')


#Affichage New Pages
def affichage_fiche_cadrage(request, livre_id):
    reset_done()
    fiche_obj = FicheCadrage.objects.filter(livre_id=livre_id).first()

    if request.method == "POST":
        fields = {
            "sujet":                    request.POST.get("sujet"),
            "hors_perimetre":           request.POST.get("hors_perimetre"),
            "contraintes_specifiques":  request.POST.get("contraintes_specifiques"),
            "cible":                    request.POST.get("cible"),
            "niveau":                   request.POST.get("niveau"),
            "objectif_lecteur":         request.POST.get("objectif_lecteur"),
            "nb_chapitre":              request.POST.get("nb_chapitre") or None,
        }
        if fiche_obj:
            for attr, val in fields.items():
                setattr(fiche_obj, attr, val)
            fiche_obj.save()
        else:
            FicheCadrage.objects.create(livre_id=livre_id, **fields)

    fiche_obj = FicheCadrage.objects.filter(livre_id=livre_id).first()

    etapes = recup_etapes(livre_id)
    return render(
        request,
        "affichage/fiche-cadrage.html",
        {
            "livre_id":     livre_id,
            "fiche":        fiche_obj,
            "etapes":       etapes,
            "current_step": 1,
            "prev_step":    "/sujet/",
            "next_step":    "/recherche/",
            "progress_pct": round(process_percent(etapes)),
        }
    )

def affichage_web_search(request, livre_id):

    # Sauvegarde POST
    if request.method == "POST":
        data = recup_web_search(livre_id) or {}

        notions = data.get("notions_indispensables") or []
        erreurs = data.get("erreurs_frequentes") or []
        etapes_es = data.get("etapes_essentielles") or []
        risques = data.get("risque") or []

        for key, value in request.POST.items():
            if key.startswith("notion_"):
                idx = int(key.split("_")[1])
                if 0 <= idx < len(notions):
                    notions[idx]["contenu"] = value

            elif key.startswith("erreur_"):
                idx = int(key.split("_")[1])
                if 0 <= idx < len(erreurs):
                    erreurs[idx]["contenu"] = value

            elif key.startswith("etape_"):
                idx = int(key.split("_")[1])
                if 0 <= idx < len(etapes_es):
                    etapes_es[idx]["contenu"] = value

            elif key.startswith("risque_"):
                idx = int(key.split("_")[1])
                if 0 <= idx < len(risques):
                    risques[idx]["contenu"] = value

        # Sauvegarder les modifications en BDD
        from .models import WebSearchSummary
        WebSearchSummary.objects.filter(livre_id=livre_id).update(
            notions_indispensables=notions,
            erreurs_frequentes=erreurs,
            etapes_essentielles=etapes_es,
            risque=risques,
        )

    # Chargement des données
    data = recup_web_search(livre_id) or {}
    print(data)
    etapes = recup_etapes(livre_id)

    return render(request, "affichage/websearch.html", context={
        "livre_id": livre_id,
        "notions": data.get("notions_indispensables") or [],
        "erreurs": data.get("erreurs_frequentes") or [],
        "etapes_es": data.get("etapes_essentielles") or [],
        "risques": data.get("risque") or [],
        "etapes": etapes,
        "current_step": 2,
        "prev_step": "/fiche-cadrage/",
        "next_step": "/plan/",
        "progress_pct": round(process_percent(etapes)),
    })
def affichage_plan_detail(request, livre_id):
    intro = Introduction.objects.filter(livre_id=livre_id).last()
    conclusion = Conclusion.objects.filter(livre_id=livre_id).last()
    fil = FilRouge.objects.filter(livre_id=livre_id).last()
    chapitres = ChapitreDetails.objects.filter(livre_id=livre_id).order_by("numero")

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

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/plan_details.html", {
        "livre_id": livre_id,
        "introduction": intro,
        "conclusion": conclusion,
        "fil_rouge": fil,
        "chapitres": chapitres,
        "etapes": etapes,
        "current_step": 3,
        "prev_step": "/recherche/",
        "next_step": "/structure/",
        "progress_pct": round(process_percent(etapes)),
    })
def affichage_structure(request, livre_id):
    chapitres = ChapitreDetails.objects.filter(livre_id=livre_id).prefetch_related("sections").order_by("numero")

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

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/structure.html", {
        "livre_id": livre_id,
        "chapitres": chapitres, "etapes" : etapes,
        "current_step": 4, "prev_step": "/plan/", "next_step": "/introduction/",
        "progress_pct": round(process_percent(etapes))
    })

def affichage_intro(request, livre_id):
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
        data = json.loads(recup_intro(livre_id))
        intro = data.get("intro")
    except Exception:
        intro = None

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/introduction.html", {
        "livre_id": livre_id,
        "intro": intro, "etapes" : etapes,
        "current_step": 5, "prev_step": "/structure/", "next_step": "/preface/",
        "progress_pct": round(process_percent(etapes))
    })
def affichage_sections_texte(request, livre_id):
    sections = recup_section_texte_all(livre_id)

    # 🔹 mapping titres
    chapitres_db = {
        c.numero: c.titre
        for c in ChapitreDetails.objects.filter(livre_id=livre_id).all()
    }

    sections_db = {
        (s.chapitre.numero, s.numero): s.titre_section
        for s in SectionDetaillee.objects.select_related("chapitre").filter(livre_id=livre_id).all()
    }

    # 🔹 mapping sections enrichies
    enrichies_db = {
        (e.chapitre, e.section): e
        for e in SectionTexteEnrichi.objects.filter(livre_id=livre_id).all()
    }

    # 🔥 UPDATE SECTION
    if request.method == "POST":
        chapitre = int(request.POST.get("chapitre"))
        section = int(request.POST.get("section"))
        contenu = request.POST.get("contenu")
        source = request.POST.get("source")  # "enrichi" ou "original"

        if source == "enrichi":
            obj = SectionTexteEnrichi.objects.filter(
                chapitre=chapitre, section=section, livre_id=livre_id
            ).first()
        else:
            obj = SectionTexte.objects.filter(
                chapitre=chapitre, section=section, livre_id=livre_id
            ).first()

        if obj:
            obj.contenu = contenu
            obj.save()

    # 🔹 enrichissement
    for s in sections:
        s["titre_chapitre"] = chapitres_db.get(s["chapitre"], f"Chapitre {s['chapitre']}")
        s["titre_section"] = sections_db.get((s["chapitre"], s["section"]), f"Section {s['section']}")

        enrichie = enrichies_db.get((s["chapitre"], s["section"]))
        if enrichie:
            s["contenu"] = enrichie.contenu
            s["source"] = "enrichi"
        else:
            s["source"] = "original"

    # 🔹 regroupement
    chapitres = {}
    for s in sections:
        chapitres.setdefault(s["chapitre"], []).append(s)

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/sections_texte.html", {
        "livre_id": livre_id,
        "chapitres": chapitres,
        "etapes": etapes,
        "current_step": 7,
        "prev_step": "/preface/",
        "next_step": "/conclusion/",
        "progress_pct": round(process_percent(etapes))
    })

def affichage_conclusion(request, livre_id):
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
        data = json.loads(recup_conclusion(livre_id))
        conclusion = data.get("conclusion")
    except Exception:
        conclusion = None

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/conclusion.html", {
        "livre_id": livre_id,
        "conclusion": conclusion, "etapes" : etapes,
        "current_step": 8, "prev_step": "/contenu/", "next_step": "/postface/",
        "progress_pct": round(process_percent(etapes))
    })

import re

from django.shortcuts import render




def affichage_preface(request, livre_id):
    preface = Preface.objects.filter(livre_id=livre_id).first()

    if request.method == "POST":
        contenu = request.POST.get("preface_contenu", "").strip()
        if contenu:
            nb_mots = len(re.findall(r"\b\w+\b", contenu, re.UNICODE))
            Preface.objects.update_or_create(
                livre_id=livre_id,
                defaults={"contenu": contenu, "nb_mots": nb_mots},
            )
            preface = Preface.objects.filter(livre_id=livre_id).first()

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/preface.html", {
        "livre_id": livre_id,
        "preface": preface,
        "etapes": etapes,
        "current_step": 6,
        "prev_step": "/introduction/",
        "next_step": "/contenu/",
        "progress_pct": round(process_percent(etapes)),
    })


def affichage_postface(request, livre_id):
    postface = Postface.objects.filter(livre_id=livre_id).first()

    if request.method == "POST":
        contenu = request.POST.get("postface_contenu", "").strip()
        if contenu:
            nb_mots = len(re.findall(r"\b\w+\b", contenu, re.UNICODE))
            Postface.objects.update_or_create(
                livre_id=livre_id,
                defaults={"contenu": contenu, "nb_mots": nb_mots},
            )
            postface = Postface.objects.filter(livre_id=livre_id).first()

    etapes = recup_etapes(livre_id)
    return render(request, "affichage/postface.html", {
        "livre_id": livre_id,
        "postface": postface,
        "etapes": etapes,
        "current_step": 9,
        "prev_step": "/conclusion/",
        "next_step": "/export/",
        "progress_pct": round(process_percent(etapes)),
    })


def fiche_cadrage_task_view(request, livre_id):
    if request.method == "POST":
        sujet = request.POST.get("sujet", "").strip()
        if sujet:
            fiche_cadrage_task.delay(sujet, livre_id)
        etapes = recup_etapes(livre_id)
        return render(request, "fiche-cadrage.html", {
            "livre_id":     livre_id,
            "sujet":        sujet,
            "etapes":       etapes,
            "current_step": 0,
            "next_step":    "/fiche-cadrage/",
            "progress_pct": round(process_percent(etapes)),
        })

    etapes = recup_etapes(livre_id)
    return render(request, "fiche-cadrage.html", {
        "livre_id":     livre_id,
        "etapes":       etapes,
        "current_step": 0,
        "next_step":    "/fiche-cadrage/",
        "progress_pct": round(process_percent(etapes)),
    })

def websearch_task_view(request, livre_id):
    reset_web_search(livre_id)
    websearch_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def plan_detail_task_view(request, livre_id):
    reset_plan_detail(livre_id)
    plan_details_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def structure_task_view(request, livre_id):
    reset_structure(livre_id)
    structure_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def introduction_task_view(request, livre_id):
    reset_intro(livre_id)
    introduction_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def gen_section_task_view(request, livre_id):
    reset_all_test(livre_id)
    generation_section_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def reprise_section_task_view(request, livre_id):
    generation_section_task.delay(livre_id, reprise=True)  # pas de reset
    return JsonResponse({"status": "ok"})


def conclusion_task_view(request, livre_id):
    reset_conclusion(livre_id)
    conclusion_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def preface_task_view(request, livre_id):
    reset_preface(livre_id)
    preface_task.delay(livre_id)
    return JsonResponse({"status": "ok"})

def postface_task_view(request, livre_id):
    reset_postface(livre_id)
    postface_task.delay(livre_id)
    return JsonResponse({"status": "ok"})





PDF_DIR = os.path.join(BASE_DIR, "Stage/fonctions/export/output")


@require_POST
def lancer_export(request, livre_id):
    try:
        data = json.loads(request.body)
        format = data.get("format", "").lower()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"ok": False, "error": "Corps JSON invalide."}, status=400)

    if format not in ("pdf", "docx", "md"):
        return JsonResponse({"ok": False, "error": f"Format '{format}' non supporté."}, status=400)

    task = export_task.delay(livre_id, format)
    return JsonResponse({"ok": True, "task_id": task.id})


def telecharger_export(request, livre_id):
    format = request.GET.get("format", "").lower()

    extensions = {"pdf": ".pdf", "docx": ".docx", "md": ".md"}
    if format not in extensions:
        raise Http404("Format non supporté.")


    file_path = OUTPUT_DIR / f"livre_{livre_id}{extensions[format]}"
    if not file_path.exists():
        raise Http404("Fichier non trouvé. Lancez d'abord l'export.")

    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or "application/octet-stream"

    response = FileResponse(open(file_path, "rb"), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="livre{extensions[format]}"'
    return response


def affichage_export(request, livre_id):
    etapes = recup_etapes(livre_id)
    return render(request, "affichage/export.html", {
        "livre_id": livre_id,
        "etapes": etapes,
        "current_step": 10,
        "prev_step": "/postface/",
        "progress_pct": round(process_percent(etapes)) if etapes else 0,
    })

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

def liste_pdfs(request):
    try:
        extensions_autorisees = (".pdf", ".md", ".docx")

        fichiers = [
            f for f in os.listdir(PDF_DIR)
            if f.lower().endswith(extensions_autorisees)
        ]

        fichiers.sort(
            key=lambda f: os.path.getmtime(os.path.join(PDF_DIR, f)),
            reverse=True
        )

    except FileNotFoundError:
        fichiers = []

    return render(request, "liste_pdfs.html", {
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

def done_fc(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.fiche_cadrage = True
    etapes.save()
    return HttpResponse(status=200)

def done_recherches(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.recherche = True
    etapes.save()
    return HttpResponse(status=200)

def done_plan(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.plan = True
    etapes.save()
    return HttpResponse(status=200)

def done_structure(livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.structure = True
    etapes.save()
    return HttpResponse(status=200)

def done_introduction(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.introduction = True
    etapes.save()
    return HttpResponse(status=200)

def done_preface(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.preface = True
    etapes.save()
    return HttpResponse(status=200)

def done_contenu(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.contenu = True
    etapes.save()
    return HttpResponse(status=200)

def done_postface(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.postface = True
    etapes.save()
    return HttpResponse(status=200)

def done_conclusion(request,livre_id):
    etapes = Etapes.objects.filter(livre_id=livre_id).first()
    etapes.conclusion = True
    etapes.save()
    return HttpResponse(status=200)


def recup_etapes(livre_id):
    etape = Etapes.objects.filter(livre_id=livre_id).first()
    steps = [
        {"num": 0,  "label": "Sujet",        "done": etape.sujet,         "link": "/sujet/"},
        {"num": 1,  "label": "Fiche cadrage","done": etape.fiche_cadrage, "link": "/fiche-cadrage/"},
        {"num": 2,  "label": "Recherche",    "done": etape.recherche,     "link": "/recherche/"},
        {"num": 3,  "label": "Plan",         "done": etape.plan,          "link": "/plan/"},
        {"num": 4,  "label": "Structure",    "done": etape.structure,     "link": "/structure/"},
        {"num": 5,  "label": "Introduction", "done": etape.introduction,  "link": "/introduction/"},
        {"num": 6,  "label": "Preface",      "done": etape.preface,       "link": "/preface/"},  # ✅
        {"num": 7,  "label": "Contenu",      "done": etape.contenu,       "link": "/contenu/"},
        {"num": 8,  "label": "Conclusion",   "done": etape.conclusion,    "link": "/conclusion/"},
        {"num": 9,  "label": "Postface",     "done": etape.postface,      "link": "/postface/"},  # ✅
        {"num": 10, "label": "Export",                                     "link": "/export/"},
    ]
    return steps

def process_percent(etapes):
    count = 0
    for etape in etapes:
        if etape.get("done"):
            count += 1
    return round(count / 7 * 100)

def init_bdd():
    Etapes.objects.all().delete()
    Etapes.objects.create()
    Variables.objects.all().delete()
    Variables.objects.create(nb_chapitre=8, nb_mots_cible=10000)

def get_livre_titre(livre_id):
    livre = Livre.objects.filter(livre_id=livre_id).first()
    return livre.livre_titre if livre else None

def supprimer_livre(livre_id):
    livre = Livre.objects.filter(livre_id=livre_id).first()
    if livre:
        livre.delete()
        reset_fiche_cadrage(livre_id)
        reset_web_search(livre_id)
        reset_plan_detail(livre_id)
        reset_structure(livre_id)
        reset_intro(livre_id)
        reset_all_test(livre_id)
        reset_conclusion(livre_id)
        reset_etapes(livre_id)

def reset_etapes(livre_id):
    Etapes.objects.filter(livre_id=livre_id).delete()

def reset_done():
    status, _ = ProcessStatus.objects.get_or_create(id=1)
    status.is_done = False
    status.save()