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
    path('', menu, name='menu'),
    path('index/', index, name='index'),

    path('process/', process_view, name='process'),

    path('progress/', progress_view, name='progress'),

    path('test/', test, name='test'),


    #Urls Affichage

    path('affichage/', menu_affichage, name='menu_affichage'),


    #Urls resets
    path('menu-reset-bdd/', menu_reset, name='menu-reset-bdd'),

    #URLs post merge

    path('fiche-cadrage/', affichage_fiche_cadrage, name='affichage_fiche_cadrage'),
    path('recherche/', affichage_web_search, name='affichage_web_search'),
    path('plan/', affichage_plan_detail, name='affichage_plan_detail'),
    path('structure/', affichage_structure, name='affichage_structure'),
    path('introduction/', affichage_intro, name='affichage_intro'),
    path('contenu/', affichage_sections_texte, name='affichage_sections_texte'),
    path('conclusion/', affichage_conclusion, name='affichage_conclusion'),


    path('sujet/', fiche_cadrage_task_view, name='fiche_cadrage'),
    path('process/web_search/', websearch_task_view, name='websearch'),
    path('process/plan_details/', plan_detail_task_view, name='plan_details'),
    path('process/structure/', structure_task_view, name='structure'),
    path('process/introduction/', introduction_task_view, name='introduction'),
    path('process/gen_sections/', gen_section_task_view, name='gen_sections'),
    path('process/conclusion/', conclusion_task_view, name='conclusion'),
    path('process/export/', export_pdf_task_view, name='export'),


    path('reset/fiche-cadrage/', reset_fiche_cadrage_view, name='reset_fiche_cadrage'),
    path('reset/websearch/', reset_web_search_view, name='reset_web_search'),
    path('reset/plandetails/', reset_plan_detail_view, name='reset_plan_detail'),
    path('reset/structure/', reset_structure_view, name='reset_structure'),
    path('reset/introduction/', reset_introduction_view, name='reset_intro'),
    path('reset/sections-texte/', reset_section_texte_view, name='reset_sections_texte'),
    path('reset/conclusion/', reset_conclusion_view, name='reset_conclusion'),
    path('reset/all/', reset_all_post_merge_view, name='reset_all'),
    path("pdfs/", liste_pdfs, name="liste_pdfs"),
    path("pdfs/<str:nom_fichier>/", telecharger_pdf, name="telecharger_pdf"),

    path("variables/", variables_affichage, name="variables"),

    path("done/fiche-cadrage/", done_fc, name="done_fc"),
]
