from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from parser import read_json_file, to_int_or_raise as _to_int

BASE_DIR = Path(__file__).resolve().parent
SECTION_DIR = BASE_DIR.parent / "section" / "output" / "section"
SECTION_FR_DIR = BASE_DIR.parent / "section" / "output" / "section_fr"
SECTION_FILE_RE = re.compile(r"^section_ch(?P<chapitre>\d+)_s(?P<section>\d+)\.json$")

def _read_json(file_path: Path, label: str) -> Any:
    return read_json_file(file_path, label, require_non_empty=False)


def _parse_section_filename(filename: str) -> tuple[int, int] | None:
    match = SECTION_FILE_RE.match(filename)
    if not match:
        return None
    chapitre = _to_int(match.group("chapitre"), "filename.chapitre")
    section = _to_int(match.group("section"), "filename.section")
    return chapitre, section


def _read_content_length(file_path: Path) -> int:
    payload = _read_json(file_path, "section")
    if not isinstance(payload, dict):
        raise ValueError(f"Format invalide (objet JSON attendu): {file_path}")

    content = payload.get("contenu", "")
    if content is None:
        content = ""
    return len(str(content))


def verify_single_section_size(
    chapitre: int,
    section: int,
    section_dir: Path = SECTION_DIR,
    section_fr_dir: Path = SECTION_FR_DIR,
) -> dict:
    """Verifie la contrainte len(section) < len(section_fr) pour une section donnee."""
    filename = f"section_ch{chapitre}_s{section}.json"
    section_path = section_dir / filename
    section_fr_path = section_fr_dir / filename

    result: dict[str, Any] = {
        "ok": True,
        "file": filename,
        "section_length": None,
        "section_fr_length": None,
        "error": None,
    }

    if not section_path.exists():
        result["ok"] = False
        result["error"] = "missing_in_section"
        return result

    if not section_fr_path.exists():
        result["ok"] = False
        result["error"] = "missing_in_section_fr"
        return result

    try:
        section_length = _read_content_length(section_path)
    except (ValueError, FileNotFoundError):
        result["ok"] = False
        result["error"] = "invalid_section_json"
        return result

    try:
        section_fr_length = _read_content_length(section_fr_path)
    except (ValueError, FileNotFoundError):
        result["ok"] = False
        result["error"] = "invalid_section_fr_json"
        return result

    result["section_length"] = section_length
    result["section_fr_length"] = section_fr_length

    if section_length >= section_fr_length:
        result["ok"] = False
        result["error"] = "invalid_order"

    return result


def verify_section_size_order(section_dir: Path = SECTION_DIR, section_fr_dir: Path = SECTION_FR_DIR) -> dict:
    """Verifie que len(section) < len(section_fr) pour chaque section_chX_sY.json."""
    report = {
        "ok": True,
        "checked": 0,
        "missing_in_section": [],
        "missing_in_section_fr": [],
        "invalid_filename": [],
        "invalid_section_json": [],
        "invalid_section_fr_json": [],
        "invalid_order": [],
    }

    if not section_dir.exists():
        report["ok"] = False
        report["missing_in_section"].append(str(section_dir))
        return report

    if not section_fr_dir.exists():
        report["ok"] = False
        report["missing_in_section_fr"].append(str(section_fr_dir))
        return report

    for section_file in sorted(section_dir.glob("section_ch*_s*.json")):
        parsed_name = _parse_section_filename(section_file.name)
        if not parsed_name:
            report["ok"] = False
            report["invalid_filename"].append(section_file.name)
            continue

        chapitre_num, section_num = parsed_name
        section_check = verify_single_section_size(
            chapitre=chapitre_num,
            section=section_num,
            section_dir=section_dir,
            section_fr_dir=section_fr_dir,
        )

        if section_check["error"] == "missing_in_section":
            report["ok"] = False
            report["missing_in_section"].append(section_file.name)
            continue

        if section_check["error"] == "missing_in_section_fr":
            report["ok"] = False
            report["missing_in_section_fr"].append(section_file.name)
            continue

        if section_check["error"] == "invalid_section_json":
            report["ok"] = False
            report["invalid_section_json"].append(section_file.name)
            continue

        if section_check["error"] == "invalid_section_fr_json":
            report["ok"] = False
            report["invalid_section_fr_json"].append(section_file.name)
            continue

        report["checked"] += 1

        if not section_check["ok"] and section_check["error"] == "invalid_order":
            report["ok"] = False
            report["invalid_order"].append(
                {
                    "file": section_file.name,
                    "section_length": section_check["section_length"],
                    "section_fr_length": section_check["section_fr_length"],
                }
            )

    return report


def _print_report(report: dict) -> None:
    print(f"Verification terminee - sections comparees: {report['checked']}")

    if report["missing_in_section"]:
        print("Fichiers manquants dans section:")
        for name in report["missing_in_section"]:
            print(f"- {name}")

    if report["missing_in_section_fr"]:
        print("Fichiers manquants dans section_fr:")
        for name in report["missing_in_section_fr"]:
            print(f"- {name}")

    if report["invalid_filename"]:
        print("Noms de fichiers invalides:")
        for name in report["invalid_filename"]:
            print(f"- {name}")

    if report["invalid_section_json"]:
        print("JSON invalides dans section:")
        for name in report["invalid_section_json"]:
            print(f"- {name}")

    if report["invalid_section_fr_json"]:
        print("JSON invalides dans section_fr:")
        for name in report["invalid_section_fr_json"]:
            print(f"- {name}")

    if report["invalid_order"]:
        print("Sections non conformes (section doit etre plus petite que section_fr):")
        for item in report["invalid_order"]:
            print(
                f"- {item['file']} | section={item['section_length']} | "
                f"section_fr={item['section_fr_length']}"
            )

    if report["ok"]:
        print("OK: toutes les sections respectent la contrainte de taille.")


if __name__ == "__main__":
    result = verify_section_size_order()
    _print_report(result)

