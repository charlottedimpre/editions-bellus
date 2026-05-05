import sys
import json
from pathlib import Path
from parser import normalize_resume_from

# Permet l'execution directe de ce fichier (python suivi.py) en resolvant les imports freres.
CURRENT_DIR = Path(__file__).resolve().parent
MAIN_DIR = CURRENT_DIR.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from conclusion.conclusion import gen_conclu
from fiche_cadrage.fiche_cadrage import fc, insert_fc
from fil_rouge.fil_rouge import gen_filrouge_with_validation
from fil_rouge.merge_filrouge import merge_filrouge_wrapper
from introduction.introduction import gen_intro
from prepostface.preface.preface import gen_preface
from prepostface.postface.postface import gen_postface
from section.section import gen_section, merge_all_chapters, load_structure
from web_search.webinput import webinput_wrapper
from web_search.web import web_search_wrapper
from web_search.webfetch import webfetch_wrapper
from web_search.weboutput import weboutput_wrapper
from plan_detaille.plan_detaille import plan_detail
from structure_chapitre.structure_chapitre import structure_chapitre
from suivi.check import check_book_progress, get_resume_instructions


def _normalize_resume_from(resume_from):
    return normalize_resume_from(resume_from)


def _run_resume_auto(auto_confirm=False, mode=None):
    instructions = get_resume_instructions()

    if not instructions.get("possible"):
        print("Aucune reprise necessaire: le pipeline semble termine.")
        return instructions

    next_step = instructions.get("next_step")
    next_function = instructions.get("next_function")
    resume_from = instructions.get("resume_from")

    print(f"Reprise automatique detectee -> etape: {next_step}")
    if resume_from:
        print(f"Point de reprise conseille: {resume_from}")

    if not next_function:
        print("Impossible de reprendre automatiquement: fonction cible introuvable.")
        return instructions

    print(f"Lancement de suivi('{next_function}')...")
    suivi(next_function, resume_from=resume_from, auto_confirm=auto_confirm, mode=mode)
    return instructions

def _section(ch_num, sec_num):
    print(f"Génération de la section {sec_num} du chapitre {ch_num}...")


def _find_start_indices(chapitres, start_from):
    if not start_from:
        return 0, 0

    target = _normalize_resume_from(start_from)
    if not target:
        print("Point de reprise invalide, reprise depuis le debut des sections.")
        return 0, 0

    for chap_idx, chap in enumerate(chapitres):
        ch_num = int(chap["numero"])
        if ch_num != target["chapitre"]:
            continue

        for sec_idx, sec in enumerate(chap.get("sections", [])):
            sec_num = int(sec["numero"])
            if sec_num == target["section"]:
                return chap_idx, sec_idx

    print("Point de reprise introuvable dans la structure, reprise depuis le debut des sections.")
    return 0, 0


def _infer_start_from_generated_sections():
    """Deduit le point de reprise a partir des fichiers deja presents dans output."""
    progress = check_book_progress()
    reprise = progress.get("reprise", {})

    if reprise.get("next_function") == "gen_all_sections" and reprise.get("resume_from"):
        return reprise.get("resume_from")

    missing_sections = progress.get("manquants", {}).get("sections_brutes", [])
    if missing_sections:
        return missing_sections[0]

    # Si toutes les sections existent mais qu'un resume de coherence manque,
    # on reprend a la section concernee pour regenerer resume + suite coherente.
    missing_resumes = progress.get("manquants", {}).get("resumes_coherence", [])
    if missing_resumes:
        return missing_resumes[0]

    return None


def suivisection(start_from=None, auto_confirm=False):
    chapitres = load_structure()
    nb_chapitres = len(chapitres)
    nb_total_sections = sum(len(ch["sections"]) for ch in chapitres)

    print(f"Structure chargée : {nb_chapitres} chapitres, {nb_total_sections} sections au total\n")

    if start_from is None:
        start_from = _infer_start_from_generated_sections()
        if start_from:
            print(f"Reprise detectee depuis les sections generees: {start_from}")

    chap_idx, sec_start_idx = _find_start_indices(chapitres, start_from)
    start_chap_idx = chap_idx

    if start_from and (chap_idx != 0 or sec_start_idx != 0):
        print(f"Reprise fine activee depuis chapitre {chapitres[chap_idx]['numero']} section {chapitres[chap_idx]['sections'][sec_start_idx]['numero']}.")

    while chap_idx < nb_chapitres:
        chap = chapitres[chap_idx]
        ch_num = int(chap["numero"])
        nb_sec = len(chap["sections"])
        print(f"Chapitre {ch_num} — {chap['titre']} ({nb_sec} sections)")
        failed_section = None

        start_idx_for_chapter = sec_start_idx if chap_idx == start_chap_idx else 0
        for sec in chap["sections"][start_idx_for_chapter:]:
            sec_num = int(sec["numero"])
            max_attempts = 25
            section_success = False
            for attempt in range(1, max_attempts + 1):
                try:
                    _section(ch_num, sec_num)
                    gen_section(ch_num, sec_num)
                    section_success = True
                    break
                except Exception as e:
                    print(f"Erreur section {sec_num} (chapitre {ch_num}) tentative {attempt}/{max_attempts}: {e}")

            if not section_success:
                failed_section = sec_num
                break

        if failed_section is not None:
            raise RuntimeError(
                f"Echec definitif: section_ch{ch_num}_s{failed_section} non generee apres {max_attempts} tentatives. "
                "Arret de l'etape sections_brutes pour eviter une validation incorrecte."
            )

        if auto_confirm:
            avis_createur = '1'
        else:
            avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")
            while avis_createur not in ['1', '2']:
                print("Le nombre entré doit être 1 ou 2.")
                avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")

        if avis_createur == '1':
            print("Étape validée")
            chap_idx += 1
            sec_start_idx = 0
        else:
            print("Étape à retravailler")
            continue


    print(f"\nGénération terminée : {nb_total_sections} sections générées pour {nb_chapitres} chapitres.")
    # Note: gen_all_sections doit être modifié afin que des tests pendant la génération complète des chapitres
    # soient effectuée



def suivi(fonction, resume_from=None, auto_confirm=False, mode=None, **_):
    if fonction == "resume_auto":
        return _run_resume_auto(auto_confirm=auto_confirm, mode=mode)

    elif fonction == "check_progress":
        progress = check_book_progress()
        print(json.dumps(progress, ensure_ascii=False, indent=2))
        return progress

    if fonction == "fc":
        fc()
        normalized_mode = str(mode).strip() if mode is not None else ""
        if normalized_mode == "1":
            insert_fc()

    elif fonction == "webinput":
        webinput_wrapper()

    elif fonction == "web_search_step":
        web_search_wrapper()

    elif fonction == "webfetch":
        webfetch_wrapper()

    elif fonction == "weboutput":
        weboutput_wrapper()

    elif fonction == "web_search":
        webinput_wrapper()
        web_search_wrapper()
        webfetch_wrapper()
        weboutput_wrapper()

    elif fonction == "plan_detail":
        plan_detail()

    elif fonction == "structure_chapitre":
        structure_chapitre(mode)

    elif fonction == "gen_intro":
        gen_intro()

    elif fonction == "gen_preface":
        gen_preface()

    elif fonction == "gen_all_sections":
        return suivisection(start_from=resume_from, auto_confirm=auto_confirm)

    elif fonction == "gen_conclu":
        gen_conclu()

    elif fonction == "gen_postface":
        gen_postface()

    elif fonction == "gen_filrouge":
        gen_filrouge_with_validation()

    elif fonction in ("merge_filrouge", "merge_filrouge_wrapper"):
        merge_filrouge_wrapper(start_from=resume_from)

    elif fonction == "merge_all_chapters":
        merge_all_chapters()

    else:
        return None

    #affichage à travailler

    if auto_confirm:
        avis_createur = '1'
    else:
        avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")
        while avis_createur not in ['1', '2']:
            print("Le nombre entré doit être 1 ou 2.")
            avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")

    if avis_createur == '1':
        print("Étape validée")
        return True
    else:
        print("Étape à retravailler")
        suivi(fonction, resume_from=resume_from, auto_confirm=auto_confirm, mode=mode)
        return None