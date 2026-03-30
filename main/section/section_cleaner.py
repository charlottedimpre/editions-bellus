import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SECTION_SUBDIR = "section_fr"


def strip_leading_title(content: str, title: str) -> tuple[str, bool, str | None]:
    """Retire un prefixe exact du type '<titre>\n' ou '<titre>\n\n' au debut du contenu."""
    separators = ("\\n\\n", "\\n", "\n\n", "\n")
    for separator in separators:
        prefix = f"{title}{separator}"
        if content.startswith(prefix):
            return content[len(prefix) :], True, separator
    return content, False, None


def normalize_section_content(raw_content):
    """Normalise differents formats de contenu section en texte exploitable."""
    if isinstance(raw_content, dict):
        return (
            raw_content.get("section_mise_a_jour")
            or raw_content.get("contenu")
            or raw_content.get("texte")
            or ""
        )

    if isinstance(raw_content, str):
        candidate = raw_content.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                decoded = json.loads(candidate)
                if isinstance(decoded, dict):
                    return (
                        decoded.get("section_mise_a_jour")
                        or decoded.get("contenu")
                        or decoded.get("texte")
                        or raw_content
                    )
            except json.JSONDecodeError:
                return raw_content
    return raw_content


def _load_titles_from_structure(structure_path: Path) -> list[str]:
    with structure_path.open("r", encoding="utf-8") as handle:
        structure = json.load(handle)

    titles: list[str] = []
    seen: set[str] = set()

    for chapitre in structure:
        chapitre_title = chapitre.get("titre")
        if isinstance(chapitre_title, str):
            cleaned = chapitre_title.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                titles.append(cleaned)

        for section in chapitre.get("sections", []):
            section_title = section.get("titre_section")
            if isinstance(section_title, str):
                cleaned = section_title.strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    titles.append(cleaned)

    return titles


def title_obliterator(section_subdir: str = DEFAULT_SECTION_SUBDIR):
    base_dir = Path(__file__).resolve().parent
    structure_path = base_dir.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
    section_dir = base_dir / "output" / section_subdir

    titles = _load_titles_from_structure(structure_path)
    patterns = [(title, re.compile(rf"\r?\n{re.escape(title)}\r?\n")) for title in titles]

    scanned_files = 0
    matches = []

    for file_path in sorted(section_dir.rglob("*.json")):
        scanned_files += 1
        with file_path.open("r", encoding="utf-8") as handle:
            section_data = json.load(handle)

        content = normalize_section_content(section_data.get("contenu", ""))
        if not isinstance(content, str) or not content:
            continue

        for title, pattern in patterns:
            if pattern.search(content):
                matches.append(
                    {
                        "fichier": str(file_path),
                        "chapitre": section_data.get("chapitre"),
                        "section": section_data.get("section"),
                        "titre_trouve": title,
                    }
                )

    return {
        "titres": titles,
        "nb_titres": len(titles),
        "nb_fichiers_scannes": scanned_files,
        "nb_occurrences": len(matches),
        "occurrences": matches,
    }


def _coerce_int(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _set_cleaned_content(section_data: dict, cleaned_content: str):
    raw_content = section_data.get("contenu", "")

    if isinstance(raw_content, dict):
        for key in ("section_mise_a_jour", "contenu", "texte"):
            if key in raw_content:
                raw_content[key] = cleaned_content
                return
        raw_content["contenu"] = cleaned_content
        return

    if isinstance(raw_content, str):
        candidate = raw_content.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                decoded = json.loads(candidate)
                if isinstance(decoded, dict):
                    for key in ("section_mise_a_jour", "contenu", "texte"):
                        if key in decoded:
                            decoded[key] = cleaned_content
                            break
                    else:
                        decoded["contenu"] = cleaned_content
                    section_data["contenu"] = json.dumps(decoded, ensure_ascii=False)
                    return
            except json.JSONDecodeError:
                pass

    section_data["contenu"] = cleaned_content


def numero_bloc_obliterator(section_subdir: str = DEFAULT_SECTION_SUBDIR):
    """Detecte les blocs NUMERO CHAPITRE/SECTION dans chaque contenu de section."""
    base_dir = Path(__file__).resolve().parent
    section_dir = base_dir / "output" / section_subdir
    filename_pattern = re.compile(r"section_ch(\d+)_s(\d+)\.json$")
    block_pattern = re.compile(
        r"NUMERO\s+CHAPITRE\s*:\s*(\d+)\s*(?:\r?\n)+\s*NUMERO\s+SECTION\s*:\s*(\d+)",
        flags=re.IGNORECASE,
    )

    scanned_files = 0
    matches = []

    for file_path in sorted(section_dir.rglob("*.json")):
        scanned_files += 1
        match_filename = filename_pattern.search(file_path.name)
        expected_chapter = int(match_filename.group(1)) if match_filename else None
        expected_section = int(match_filename.group(2)) if match_filename else None

        with file_path.open("r", encoding="utf-8") as handle:
            section_data = json.load(handle)

        content = normalize_section_content(section_data.get("contenu", ""))
        if not isinstance(content, str) or not content:
            continue

        for block in block_pattern.finditer(content):
            found_chapter = int(block.group(1))
            found_section = int(block.group(2))
            json_chapter = _coerce_int(section_data.get("chapitre"))
            json_section = _coerce_int(section_data.get("section"))

            mismatch_file = (
                expected_chapter is not None
                and expected_section is not None
                and (found_chapter != expected_chapter or found_section != expected_section)
            )
            mismatch_json = (
                json_chapter is not None
                and json_section is not None
                and (found_chapter != json_chapter or found_section != json_section)
            )

            matches.append(
                {
                    "fichier": str(file_path),
                    "trouve": {
                        "chapitre": found_chapter,
                        "section": found_section,
                    },
                    "attendu_fichier": {
                        "chapitre": expected_chapter,
                        "section": expected_section,
                    },
                    "attendu_json": {
                        "chapitre": json_chapter,
                        "section": json_section,
                    },
                    "mismatch_fichier": mismatch_file,
                    "mismatch_json": mismatch_json,
                    "extrait": block.group(0),
                }
            )

    mismatches = [item for item in matches if item["mismatch_fichier"] or item["mismatch_json"]]

    return {
        "nb_fichiers_scannes": scanned_files,
        "nb_occurrences": len(matches),
        "nb_mismatches": len(mismatches),
        "occurrences": matches,
        "mismatches": mismatches,
    }


def _remove_false_phrases_from_content(content: str) -> tuple[str, list[str]]:
    """Supprime les blocs isoles qui ressemblent a des fausses phrases/intertitres."""

    def _starts_with_uppercase_letter(text: str) -> bool:
        for char in text:
            if char.isalpha():
                return char.isupper()
        return False

    def _has_sentence_ending_punctuation(text: str) -> bool:
        return text.endswith((".", "!", "?", "…"))

    def _is_false_heading_line(text: str) -> bool:
        words = [word for word in re.split(r"\s+", text) if word]
        if not words or len(words) > 14:
            return False
        if not _starts_with_uppercase_letter(text):
            return False
        if _has_sentence_ending_punctuation(text):
            return False
        if text.endswith(":"):
            return False
        # Evite de supprimer des lignes techniques qui contiennent des marqueurs.
        if re.search(r"[:;=/_\\]", text):
            return False
        return True

    def _looks_like_paragraph_line(text: str) -> bool:
        words = [word for word in re.split(r"\s+", text) if word]
        return len(words) >= 8 or _has_sentence_ending_punctuation(text)

    def _neighbor_non_empty_line(lines: list[str], index: int, step: int) -> str | None:
        cursor = index + step
        while 0 <= cursor < len(lines):
            candidate = lines[cursor].strip()
            if candidate:
                return candidate
            cursor += step
        return None

    lines = content.splitlines()
    removed: list[str] = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not _is_false_heading_line(stripped):
            continue

        prev_line = _neighbor_non_empty_line(lines, index, -1)
        next_line = _neighbor_non_empty_line(lines, index, 1)

        prev_is_paragraph = bool(prev_line and _looks_like_paragraph_line(prev_line))
        next_is_paragraph = bool(next_line and _looks_like_paragraph_line(next_line))

        if prev_is_paragraph or next_is_paragraph:
            removed.append(stripped)
            lines[index] = ""

    content = "\n".join(lines)

    parts = re.split(r"(\n\s*\n)", content)

    for index in range(0, len(parts), 2):
        block = parts[index]
        if not block.strip():
            continue

        has_separator_before = index > 0
        has_separator_after = index + 1 < len(parts)
        normalized_block = " ".join(line.strip() for line in block.splitlines() if line.strip())

        if (
            normalized_block
            and _is_false_heading_line(normalized_block)
            and not _has_sentence_ending_punctuation(normalized_block)
        ):
            removed.append(normalized_block)
            parts[index] = ""

    cleaned = "".join(parts)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, removed


def false_phrase_obliterator(section_subdir: str = DEFAULT_SECTION_SUBDIR):
    """Detecte les blocs de texte isoles sans ponctuation finale de phrase."""
    base_dir = Path(__file__).resolve().parent
    section_dir = base_dir / "output" / section_subdir

    scanned_files = 0
    matches = []

    for file_path in sorted(section_dir.rglob("*.json")):
        scanned_files += 1

        with file_path.open("r", encoding="utf-8") as handle:
            section_data = json.load(handle)

        content = normalize_section_content(section_data.get("contenu", ""))
        if not isinstance(content, str) or not content:
            continue

        _, removed_blocks = _remove_false_phrases_from_content(content)
        for block in removed_blocks:
            matches.append(
                {
                    "fichier": str(file_path),
                    "chapitre": section_data.get("chapitre"),
                    "section": section_data.get("section"),
                    "extrait": block[:200],
                }
            )

    return {
        "nb_fichiers_scannes": scanned_files,
        "nb_occurrences": len(matches),
        "occurrences": matches,
    }


def auto_clean_section_errors(
    remove_all_numero_blocks: bool = True,
    remove_false_phrases: bool = True,
    section_subdir: str = DEFAULT_SECTION_SUBDIR,
):
    """Lance les detecteurs, nettoie les erreurs detectees et sauvegarde un rapport."""
    title_report = title_obliterator(section_subdir=section_subdir)
    numero_report = numero_bloc_obliterator(section_subdir=section_subdir)
    false_phrase_report = (
        false_phrase_obliterator(section_subdir=section_subdir)
        if remove_false_phrases
        else {"nb_fichiers_scannes": 0, "nb_occurrences": 0, "occurrences": []}
    )

    title_occurrences: list[dict[str, Any]] = title_report["occurrences"]
    numero_occurrences: list[dict[str, Any]] = numero_report["occurrences"]
    numero_mismatches: list[dict[str, Any]] = numero_report["mismatches"]
    false_phrase_occurrences: list[dict[str, Any]] = false_phrase_report["occurrences"]

    title_patterns = {
        title: re.compile(rf"\r?\n{re.escape(title)}\r?\n")
        for title in {item["titre_trouve"] for item in title_occurrences}
    }

    numero_targets = numero_occurrences if remove_all_numero_blocks else numero_mismatches

    cleanup_targets: dict[str, dict] = {}

    for occurrence in title_occurrences:
        file_path = occurrence["fichier"]
        target = cleanup_targets.setdefault(
            file_path,
            {"titles": set(), "numero_blocks": [], "remove_false_phrases": False},
        )
        target["titles"].add(occurrence["titre_trouve"])

    for occurrence in numero_targets:
        file_path = occurrence["fichier"]
        target = cleanup_targets.setdefault(
            file_path,
            {"titles": set(), "numero_blocks": [], "remove_false_phrases": False},
        )
        target["numero_blocks"].append(occurrence["extrait"])

    for occurrence in false_phrase_occurrences:
        file_path = occurrence["fichier"]
        target = cleanup_targets.setdefault(
            file_path,
            {"titles": set(), "numero_blocks": [], "remove_false_phrases": False},
        )
        target["remove_false_phrases"] = True

    files_updated = 0
    details = []

    for file_name, target in cleanup_targets.items():
        file_path = Path(file_name)
        with file_path.open("r", encoding="utf-8") as handle:
            section_data = json.load(handle)

        original_content = normalize_section_content(section_data.get("contenu", ""))
        if not isinstance(original_content, str) or not original_content:
            continue

        cleaned_content = original_content
        removed_titles = 0
        removed_numero_blocks = 0
        removed_false_phrases = 0

        for title in target["titles"]:
            pattern = title_patterns[title]
            cleaned_content, removed = pattern.subn("\n", cleaned_content)
            removed_titles += removed

        for block in target["numero_blocks"]:
            occurrences = cleaned_content.count(block)
            if occurrences:
                cleaned_content = cleaned_content.replace(block, "", occurrences)
                removed_numero_blocks += occurrences

        if target["remove_false_phrases"]:
            cleaned_content, removed_blocks = _remove_false_phrases_from_content(cleaned_content)
            removed_false_phrases = len(removed_blocks)

        cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content).strip()

        if cleaned_content == original_content:
            continue

        _set_cleaned_content(section_data, cleaned_content)
        with file_path.open("w", encoding="utf-8") as handle:
            json.dump(section_data, handle, ensure_ascii=False, indent=2)

        files_updated += 1
        details.append(
            {
                "fichier": str(file_path),
                "titres_supprimes": removed_titles,
                "blocs_numero_supprimes": removed_numero_blocks,
                "fausses_phrases_supprimees": removed_false_phrases,
            }
        )

    base_dir = Path(__file__).resolve().parent
    report_dir = base_dir / "output"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"cleaner_report_{timestamp}.json"

    report = {
        "date": timestamp,
        "parametres": {
            "section_subdir": section_subdir,
            "remove_all_numero_blocks": remove_all_numero_blocks,
            "remove_false_phrases": remove_false_phrases,
        },
        "title_report": {
            "nb_fichiers_scannes": title_report["nb_fichiers_scannes"],
            "nb_occurrences": title_report["nb_occurrences"],
        },
        "numero_report": {
            "nb_fichiers_scannes": numero_report["nb_fichiers_scannes"],
            "nb_occurrences": numero_report["nb_occurrences"],
            "nb_mismatches": numero_report["nb_mismatches"],
        },
        "false_phrase_report": {
            "nb_fichiers_scannes": false_phrase_report["nb_fichiers_scannes"],
            "nb_occurrences": false_phrase_report["nb_occurrences"],
        },
        "nettoyage": {
            "nb_fichiers_modifies": files_updated,
            "details": details,
        },
    }

    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print({
        "report_path": str(report_path),
        "nb_fichiers_modifies": files_updated,
        "details": details,
        "title_report": title_report,
        "numero_report": numero_report,
    })
