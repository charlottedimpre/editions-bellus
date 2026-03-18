from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "main"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from conclusion.conclusion import gen_conclu
from fiche_cadrage.fiche_cadrage import fc
from fil_rouge.fil_rouge import gen_filrouge
from fil_rouge.merge_filrouge import merge_filrouge_wrapper
from introduction.introduction import gen_intro
from section.section import gen_all_sections, merge_all_chapters
from web_search.webinput import webinput_wrapper
from web_search.web import web_search_wrapper
from web_search.webfetch import webfetch_wrapper
from web_search.weboutput import weboutput_wrapper
from plan_detaille.plan_detaille import plan_detail
from structure_chapitre.structure_chapitre import structure_chapitre

def finalize():
    intro_path = ROOT_DIR / "main" / "introduction" / "output" / "introduction.json"
    with intro_path.open("r", encoding="utf-8") as f:
        intro = f.read()

    sommaire_path = ROOT_DIR / "main" / "structure_chapitre" / "output" / "structure_chapitre.json"
    with sommaire_path.open("r", encoding="utf-8") as f:
        sommaire = f.read()

    conclu_path = ROOT_DIR / "main" / "conclusion" / "output" / "conclusion.json"
    with conclu_path.open("r", encoding="utf-8") as f:
        conclu = f.read()

    # TODO: merge intro, sommaire, conclu, and all chapters into a single final document.

def restart():
    paths = [
        ROOT_DIR / "main" / "fiche_cadrage" / "output",
        ROOT_DIR / "main" / "web_search" / "output",
        ROOT_DIR / "main" / "plan_detaille" / "output",
        ROOT_DIR / "main" / "structure_chapitre" / "output",
        ROOT_DIR / "main" / "introduction" / "output",
        ROOT_DIR / "main" / "section" / "output" / "section",
        ROOT_DIR / "main" / "section" / "output" / "resume",
        ROOT_DIR / "main" / "conclusion" / "output",
        ROOT_DIR / "main" / "fil_rouge" / "output",
        ROOT_DIR / "main" / "section" / "output" / "section_fr",
        ROOT_DIR / "main" / "section" / "output" / "chapitre",
    ]

    for path in paths:
        if not path.exists() or not path.is_dir():
            continue
        for file in path.rglob("*"):
            if file.is_file():
                file.unlink()



if __name__ == '__main__':
    inputthething = input("Est ce que tu veux redémarrer le projet (1), ou lancer la génération (2) ? ")
    while inputthething not in ['1', '2']:
        print("Le nombre entré doit être 1 ou 2.")
        inputthething = input("Est ce que tu veux redémarrer le projet (1), ou lancer la génération (2) ? ")

    if inputthething == '1':
        restart()
        print("Projet redémarré. Tous les fichiers de sortie ont été supprimés.")
    else:
        #fc()

        # web search
        #webinput_wrapper()
        #web_search_wrapper()
        #webfetch_wrapper()
        #weboutput_wrapper()


        #plan_detail()
        #structure_chapitre()
        #gen_intro()
        #gen_all_sections()
        #gen_conclu()
        #gen_filrouge()
        merge_filrouge_wrapper()
        #merge_all_chapters()