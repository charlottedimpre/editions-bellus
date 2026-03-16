import os
from pathlib import Path
import sys

# Ensure imports target the `main/` source directory, not this `main.py` file.
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
    intro_path = os.path.join("main", "introduction", "output", "introduction.json")
    with open(intro_path, "r", encoding="utf-8") as f:
        intro = f.read()

    sommaire_path = os.path.join("main", "structure_chapitre", "output", "structure_chapitre.json")
    with open(sommaire_path, "r", encoding="utf-8") as f:
        sommaire = f.read()

    conclu_path = os.path.join("main", "conclusion", "output", "conclusion.json")
    with open(conclu_path, "r", encoding="utf-8") as f:
        conclu = f.read()

    # TODO: merge intro, sommaire, conclu, and all chapters into a single final document.


if __name__ == '__main__':
    fc()

    # web search
    webinput_wrapper()
    web_search_wrapper()
    webfetch_wrapper()
    weboutput_wrapper()

    plan_detail()
    structure_chapitre()
    gen_intro()
    gen_all_sections()
    gen_conclu()
    gen_filrouge()
    merge_filrouge_wrapper()
    merge_all_chapters()