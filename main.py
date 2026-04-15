from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "main"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from suivi.suivi import suivi
from section.section_cleaner import auto_clean_section_errors
from affichage.affichage import affichage


def get_restart_paths():
    return [
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


def clear_output_path(path):
    if not path.exists() or not path.is_dir():
        return False

    for file in path.rglob("*"):
        if file.is_file():
            file.unlink()
    return True


def restart(target_path=None):
    paths = [target_path] if target_path else get_restart_paths()

    for path in paths:
        clear_output_path(path)


def choose_restart_paths_from_index():
    paths = get_restart_paths()
    print("Choisis le dossier a partir duquel vider :")
    for index, path in enumerate(paths, start=1):
        print(f"{index}. {path.relative_to(ROOT_DIR)}")

    selected = input("Numero du dossier de depart : ")
    while not selected.isdigit() or not (1 <= int(selected) <= len(paths)):
        print(f"Le nombre entre doit etre entre 1 et {len(paths)}.")
        selected = input("Numero du dossier de depart : ")

    return paths[int(selected) - 1 :]


def run_resume_until_done(max_cycles=20):
    last_signature = None

    for _ in range(max_cycles):
        instructions = suivi("resume_auto", auto_confirm=True)
        if not isinstance(instructions, dict):
            print("Arret reprise auto: reponse inattendue.")
            return False

        if not instructions.get("possible"):
            print("Reprise automatique terminee.")
            return True

        signature = (
            instructions.get("next_step"),
            str(instructions.get("resume_from")),
        )
        if signature == last_signature:
            print("Arret reprise auto: progression bloquee, verification manuelle conseillee.")
            return False
        last_signature = signature

    print("Arret reprise auto: limite de cycles atteinte.")
    return False


def run_generation_with_auto_resume():
    print("Generation/reprise automatique en cours...")
    completed = run_resume_until_done()
    if completed:
        auto_clean_section_errors(remove_all_numero_blocks=True, section_subdir="section_fr")
        print("Generation terminee.")



def ask_menu_choice():
    prompt = (
        "Tu veux redemarrer tout le projet (1), lancer la generation/reprise auto (2), "
        "vider un seul dossier (3), generer le PDF (4), ou quitter (5) ? "
    )
    valid_choices = {"1", "2", "3", "4", "5"}

    choice = input(prompt)
    while choice not in valid_choices:
        print("Le nombre entre doit etre 1, 2, 3, 4 ou 5.")
        choice = input(prompt)
    return choice


def handle_partial_cleanup():
    selected_paths = choose_restart_paths_from_index()
    for selected_path in selected_paths:
        if clear_output_path(selected_path):
            print(f"Dossier vide: {selected_path.relative_to(ROOT_DIR)}")
        else:
            print(f"Dossier introuvable ou invalide: {selected_path.relative_to(ROOT_DIR)}")


if __name__ == '__main__':
    while True:
        choice = ask_menu_choice()

        if choice == '1':
            restart()
            print("Projet redemarre. Tous les fichiers de sortie ont ete supprimes.")
        elif choice == '2':
            run_generation_with_auto_resume()
        elif choice == '3':
            handle_partial_cleanup()
        elif choice == '4':
            affichage()
            print("PDF genere.")
        else:
            print("Au revoir !")
            break
