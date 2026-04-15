import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MAIN_DIR = BASE_DIR.parent


def _json_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def _safe_load_json(path: Path):
    if not _json_exists(path):
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _count_json_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return len([p for p in path.glob("*.json") if p.is_file()])


def _collect_expected_pairs(structure_data) -> list[tuple[int, int]]:
    """Retourne la liste attendue des couples (chapitre, section)."""
    pairs = []
    if not isinstance(structure_data, list):
        return pairs

    for chapitre in structure_data:
        if not isinstance(chapitre, dict):
            continue
        try:
            ch_num = int(chapitre.get("numero"))
        except (TypeError, ValueError):
            continue

        sections = chapitre.get("sections", [])
        if not isinstance(sections, list):
            continue

        for sec in sections:
            if not isinstance(sec, dict):
                continue
            try:
                sec_num = int(sec.get("numero"))
            except (TypeError, ValueError):
                continue
            pairs.append((ch_num, sec_num))

    pairs.sort(key=lambda p: (p[0], p[1]))
    return pairs


def _collect_missing_pairs(directory: Path, expected_pairs: list[tuple[int, int]], prefix: str) -> list[dict]:
    missing = []
    for ch_num, sec_num in expected_pairs:
        candidate = directory / f"{prefix}_ch{ch_num}_s{sec_num}.json"
        if not candidate.exists():
            missing.append({"chapitre": ch_num, "section": sec_num})
    return missing


def _collect_missing_chapters(directory: Path, expected_chapters: list[int]) -> list[int]:
    missing = []
    for chapter_num in expected_chapters:
        candidate = directory / f"chapitre_{chapter_num}.json"
        if not candidate.exists():
            missing.append(chapter_num)
    return missing


def _previous_pair(expected_pairs: list[tuple[int, int]], pair: dict) -> dict | None:
    ordered = [{"chapitre": ch, "section": sec} for ch, sec in expected_pairs]
    for idx, item in enumerate(ordered):
        if item["chapitre"] == pair.get("chapitre") and item["section"] == pair.get("section"):
            if idx == 0:
                return None
            return ordered[idx - 1]
    return None


def _resolve_section_start(
    candidate: dict,
    expected_pairs: list[tuple[int, int]],
    missing_resumes: list[dict],
) -> dict:
    """Recule au besoin pour garantir que la coherence precedente existe."""
    missing_resume_set = {(m["chapitre"], m["section"]) for m in missing_resumes}
    start = dict(candidate)

    while True:
        prev = _previous_pair(expected_pairs, start)
        if prev is None:
            return start

        prev_key = (prev["chapitre"], prev["section"])
        if prev_key in missing_resume_set:
            start = prev
            continue
        return start


def _resolve_web_resume_target() -> tuple[str, str]:
    """Determine la prochaine sous-etape web a lancer selon les artefacts disponibles."""
    web_output_dir = MAIN_DIR / "web_search" / "output"
    ws_search_path = web_output_dir / "ws_search.json"
    ws_pertinent_path = web_output_dir / "ws_pertinent.json"
    ws_content_path = web_output_dir / "ws_content.json"

    if _json_exists(ws_content_path):
        return "weboutput", "weboutput"
    if _json_exists(ws_pertinent_path):
        return "webfetch", "webfetch"
    if _json_exists(ws_search_path):
        return "web_search", "web_search_step"
    return "webinput", "webinput"


def _build_resume_plan(progress_data: dict, expected_pairs: list[tuple[int, int]]) -> dict:
    """Construit un plan de reprise concret base sur les outputs manquants."""
    steps = progress_data.get("etapes", {})
    missing = progress_data.get("manquants", {})

    # Etapes lineaires avant la generation des sections
    if not steps.get("fiche_cadrage", False):
        return {
            "possible": True,
            "next_step": "fiche_cadrage",
            "next_function": "fc",
            "resume_from": None,
        }

    if not steps.get("web_search", False):
        web_step, web_function = _resolve_web_resume_target()
        return {
            "possible": True,
            "next_step": web_step,
            "next_function": web_function,
            "resume_from": None,
        }

    prereq_map = [
        ("plan_detaille", "plan_detail"),
        ("structure_chapitre", "structure_chapitre"),
        ("introduction", "gen_intro"),
    ]
    for step_name, function_name in prereq_map:
        if not steps.get(step_name, False):
            return {
                "possible": True,
                "next_step": step_name,
                "next_function": function_name,
                "resume_from": None,
            }

    # Reprise des sections
    missing_sections = missing.get("sections_brutes", [])
    missing_resumes = missing.get("resumes_coherence", [])

    if missing_sections:
        start = _resolve_section_start(missing_sections[0], expected_pairs, missing_resumes)
        return {
            "possible": True,
            "next_step": "sections_brutes",
            "next_function": "gen_all_sections",
            "resume_from": start,
        }

    if missing_resumes:
        start = _resolve_section_start(missing_resumes[0], expected_pairs, missing_resumes)
        return {
            "possible": True,
            "next_step": "resumes_coherence",
            "next_function": "gen_all_sections",
            "resume_from": start,
        }

    if not steps.get("conclusion", False):
        return {
            "possible": True,
            "next_step": "conclusion",
            "next_function": "gen_conclu",
            "resume_from": None,
        }

    if not steps.get("fil_rouge", False):
        return {
            "possible": True,
            "next_step": "fil_rouge",
            "next_function": "gen_filrouge",
            "resume_from": None,
        }

    missing_sections_fr = missing.get("sections_fil_rouge", [])
    if missing_sections_fr:
        return {
            "possible": True,
            "next_step": "sections_fil_rouge",
            "next_function": "merge_filrouge_wrapper",
            "resume_from": missing_sections_fr[0],
        }

    missing_chapters = missing.get("chapitres_fusionnes", [])
    if missing_chapters:
        return {
            "possible": True,
            "next_step": "chapitres_fusionnes",
            "next_function": "merge_all_chapters",
            "resume_from": {"chapitre": missing_chapters[0]},
        }

    return {
        "possible": False,
        "next_step": "termine",
        "next_function": None,
        "resume_from": None,
    }


def check_book_progress() -> dict:
    """Inspecte les dossiers output et retourne l'etat d'avancement du livre."""
    fiche_path = MAIN_DIR / "fiche_cadrage" / "output" / "fiche_cadrage.json"
    ws_final_path = MAIN_DIR / "web_search" / "output" / "ws_final.json"
    plan_path = MAIN_DIR / "plan_detaille" / "output" / "plan_detaille.json"
    structure_path = MAIN_DIR / "structure_chapitre" / "output" / "structure_chapitre.json"
    intro_path = MAIN_DIR / "introduction" / "output" / "introduction.json"
    conclusion_path = MAIN_DIR / "conclusion" / "output" / "conclusion.json"
    fil_rouge_path = MAIN_DIR / "fil_rouge" / "output" / "fil_rouge.json"

    section_output_dir = MAIN_DIR / "section" / "output"
    section_dir = section_output_dir / "section"
    resume_dir = section_output_dir / "resume"
    section_fr_dir = section_output_dir / "section_fr"
    chapitre_dir = section_output_dir / "chapitre"

    structure_data = _safe_load_json(structure_path)
    expected_pairs = _collect_expected_pairs(structure_data)
    expected_chapters = sorted({pair[0] for pair in expected_pairs})

    expected_sections_count = len(expected_pairs)
    expected_chapters_count = len(expected_chapters)

    section_count = _count_json_files(section_dir)
    resume_count = _count_json_files(resume_dir)
    section_fr_count = _count_json_files(section_fr_dir)
    chapitre_count = _count_json_files(chapitre_dir)

    missing_sections = _collect_missing_pairs(section_dir, expected_pairs, "section")
    missing_resumes = _collect_missing_pairs(resume_dir, expected_pairs, "coherence")
    missing_sections_fr = _collect_missing_pairs(section_fr_dir, expected_pairs, "section")
    missing_chapitres = _collect_missing_chapters(chapitre_dir, expected_chapters)

    steps = {
        "fiche_cadrage": _json_exists(fiche_path),
        "web_search": _json_exists(ws_final_path),
        "plan_detaille": _json_exists(plan_path),
        "structure_chapitre": _json_exists(structure_path),
        "introduction": _json_exists(intro_path),
        "sections_brutes": expected_sections_count > 0 and not missing_sections,
        "resumes_coherence": expected_sections_count > 0 and not missing_resumes,
        "conclusion": _json_exists(conclusion_path),
        "fil_rouge": _json_exists(fil_rouge_path),
        "sections_fil_rouge": expected_sections_count > 0 and not missing_sections_fr,
        "chapitres_fusionnes": expected_chapters_count > 0 and not missing_chapitres,
    }

    ordered_steps = [
        "fiche_cadrage",
        "web_search",
        "plan_detaille",
        "structure_chapitre",
        "introduction",
        "sections_brutes",
        "resumes_coherence",
        "conclusion",
        "fil_rouge",
        "sections_fil_rouge",
        "chapitres_fusionnes",
    ]

    current_step = "aucune_generation"
    for step_name in ordered_steps:
        if steps[step_name]:
            current_step = step_name
        else:
            break

    completed_steps = sum(1 for done in steps.values() if done)
    progress_percent = round((completed_steps / len(ordered_steps)) * 100, 2)

    progress = {
        "etape_actuelle": current_step,
        "progression_pourcent": progress_percent,
        "etapes": steps,
        "compteurs": {
            "chapitres_attendus": expected_chapters_count,
            "chapitres_fusionnes": chapitre_count,
            "sections_attendues": expected_sections_count,
            "sections_brutes": section_count,
            "resumes_coherence": resume_count,
            "sections_fil_rouge": section_fr_count,
        },
        "manquants": {
            "sections_brutes": missing_sections,
            "resumes_coherence": missing_resumes,
            "sections_fil_rouge": missing_sections_fr,
            "chapitres_fusionnes": missing_chapitres,
        },
    }
    progress["reprise"] = _build_resume_plan(progress, expected_pairs)
    return progress


def get_resume_instructions() -> dict:
    """Fonction prete a l'emploi pour reprendre apres interruption."""
    return check_book_progress().get("reprise", {})


if __name__ == "__main__":
    result = check_book_progress()
    print(json.dumps(result, ensure_ascii=False, indent=2))

