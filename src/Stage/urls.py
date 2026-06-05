"""
URL configuration for Stage project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from dotenv import variables

from .views import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', menu_redirect, name='menu'),

    path('progress/', progress_view, name='progress'),



    #Urls Affichage


    #Urls resets
    path('menu-reset-bdd/', menu_reset, name='menu-reset-bdd'),

    #URLs post merge

    path('<int:livre_id>/fiche-cadrage/', affichage_fiche_cadrage, name='affichage_fiche_cadrage'),
    path('<int:livre_id>/recherche/', affichage_web_search, name='affichage_web_search'),
    path('<int:livre_id>/plan/', affichage_plan_detail, name='affichage_plan_detail'),
    path('<int:livre_id>/structure/', affichage_structure, name='affichage_structure'),
    path('<int:livre_id>/introduction/', affichage_intro, name='affichage_intro'),
    path('<int:livre_id>/contenu/', affichage_sections_texte, name='affichage_sections_texte'),
    path('<int:livre_id>/conclusion/', affichage_conclusion, name='affichage_conclusion'),
    path('<int:livre_id>/preface/', affichage_preface, name='affichage_preface'),
    path('<int:livre_id>/postface/', affichage_postface, name='affichage_postface'),
    path('<int:livre_id>/export/', affichage_export, name='affichage_export'),

    path("<int:livre_id>/export/lancer/", lancer_export, name="lancer_export"),
    path("<int:livre_id>/export/telecharger/", telecharger_export, name="telecharger_export"),

    path('<int:livre_id>/sujet/', fiche_cadrage_task_view, name='fiche_cadrage'),
    path('process/<int:livre_id>/web_search/', websearch_task_view, name='websearch'),
    path('process/<int:livre_id>/plan_details/', plan_detail_task_view, name='plan_details'),
    path('process/<int:livre_id>/structure/', structure_task_view, name='structure'),
    path('process/<int:livre_id>/introduction/', introduction_task_view, name='introduction'),
    path('process/<int:livre_id>/gen_sections/', gen_section_task_view, name='gen_sections'),
    path('process/<int:livre_id>/reprise/', reprise_section_task_view, name='reprise_sections'),
    path('process/<int:livre_id>/conclusion/', conclusion_task_view, name='conclusion'),
    path('process/<int:livre_id>/preface/', preface_task_view, name='preface'),
    path('process/<int:livre_id>/postface/', postface_task_view, name='postface'),


    path("variables/", variables_affichage, name="variables"),

    path("done/<int:livre_id>/fiche-cadrage/", done_fc, name="done_fc"),
    path("done/<int:livre_id>/recherches/", done_recherches, name="done_recherches"),
    path("done/<int:livre_id>/plan/", done_plan, name="done_plan"),
    path("done/<int:livre_id>/structure/", done_structure, name="done_structure"),
    path("done/<int:livre_id>/introduction/", done_introduction, name="done_introduction"),
    path("done/<int:livre_id>/preface/", done_preface, name="done_preface"),
    path("done/<int:livre_id>/contenu/", done_contenu, name="done_contenu"),
    path("done/<int:livre_id>/conclusion/", done_conclusion, name="done_conclusion"),
    path("done/<int:livre_id>/postface/", done_postface, name="done_postface"),

    path("livres/", livres, name="livres"),
    path("export/", liste_pdfs, name="liste_pdfs"),
    path("export/", liste_pdfs, name="liste_pdfs"),
    path("pdfs/<str:nom_fichier>/", telecharger_pdf, name="telecharger_pdf"),

]
