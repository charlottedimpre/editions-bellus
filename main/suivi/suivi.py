import sys
from pathlib import Path

# Permet l'execution directe de ce fichier (python suivi.py) en resolvant les imports freres.
CURRENT_DIR = Path(__file__).resolve().parent
MAIN_DIR = CURRENT_DIR.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from conclusion.conclusion import gen_conclu
from fiche_cadrage.fiche_cadrage import fc
from fil_rouge.fil_rouge import gen_filrouge
from fil_rouge.merge_filrouge import merge_filrouge_wrapper
from introduction.introduction import gen_intro
from section.section import gen_section, merge_all_chapters, load_structure
from web_search.webinput import webinput_wrapper
from web_search.web import web_search_wrapper
from web_search.webfetch import webfetch_wrapper
from web_search.weboutput import weboutput_wrapper
from plan_detaille.plan_detaille import plan_detail
from structure_chapitre.structure_chapitre import structure_chapitre

def _section(ch_num, sec_num):
    print(f"Génération de la section {sec_num} du chapitre {ch_num}...")

def suivisection():
    chapitres = load_structure()
    nb_chapitres = len(chapitres)
    nb_total_sections = sum(len(ch["sections"]) for ch in chapitres)

    print(f"Structure chargée : {nb_chapitres} chapitres, {nb_total_sections} sections au total\n")

    chap_idx = 0
    while chap_idx < nb_chapitres:
        chap = chapitres[chap_idx]
        ch_num = int(chap["numero"])
        nb_sec = len(chap["sections"])
        print(f"Chapitre {ch_num} — {chap['titre']} ({nb_sec} sections)")

        for sec in chap["sections"]:
            sec_num = int(sec["numero"])
            max_attempts = 10
            for attempt in range(1, max_attempts + 1):
                try:
                    _section(ch_num, sec_num)
                    gen_section(ch_num, sec_num)
                    break
                except Exception as e:
                    print(f"Erreur section {sec_num} (chapitre {ch_num}) tentative {attempt}/{max_attempts}: {e}")

        # affichage à chaque chapitre smh
        avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")
        while avis_createur not in ['1', '2']:
            print("Le nombre entré doit être 1 ou 2.")
            avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")

        if avis_createur == '1':
            print("Étape validée")
            chap_idx += 1
        else:
            print("Étape à retravailler")
            continue


    print(f"\nGénération terminée : {nb_total_sections} sections générées pour {nb_chapitres} chapitres.")
    # Note: gen_all_sections doit être modifié afin que des tests pendant la génération complète des chapitres
    # soient effectuée



def suivi(fonction):
    if fonction == "fc":
        fc()

    elif fonction == "web_search":
        webinput_wrapper()
        web_search_wrapper()
        webfetch_wrapper()
        weboutput_wrapper()

    elif fonction == "plan_detail":
        plan_detail()

    elif fonction == "structure_chapitre":
        structure_chapitre()

    elif fonction == "gen_intro":
        gen_intro()

    elif fonction =="gen_all_sections":
        suivisection()
        return None

    elif fonction == "gen_conclu":
        gen_conclu()

    elif fonction == "gen_filrouge":
        gen_filrouge()

    elif fonction == "merge_filrouge":
        merge_filrouge_wrapper()

    elif fonction == "merge_all_chapters":
        merge_all_chapters()

    else:
        return None

    #affichage à travailler

    avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")
    while avis_createur not in ['1', '2']:
        print("Le nombre entré doit être 1 ou 2.")
        avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")

    if avis_createur == '1':
        print("Étape validée")
        return True
    else:
        print("Étape à retravailler")
        suivi(fonction)
        return None