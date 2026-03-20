from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "main"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from suivi.suivi import suivi


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
        suivi("fc")

        suivi("web_search")

        suivi("plan_detail")
        suivi("structure_chapitre")

        suivi("gen_intro")
        suivi("gen_all_sections")
        suivi("gen_conclu")

        suivi("gen_filrouge")
        suivi("merge_filrouge_wrapper")
        suivi("merge_all_chapters")