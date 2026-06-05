"""
verification_filrouge.py — adapté BDD.
Vérifie que chaque section de la structure a une insertion FilRouge en BDD.
"""
from __future__ import annotations

import json
from typing import Any

from ...models import FilRougeInsertion
from ..structure_chapitre import recup_chapitres_sections


def verify_all_sections_have_filrouge_entry(livre_id: int) -> dict[str, Any]:
    """Vérifie que chaque section de la structure a une insertion fil rouge en BDD."""
    structure_data = json.loads(recup_chapitres_sections(livre_id))
    if not isinstance(structure_data, list):
        raise ValueError("La structure des chapitres doit etre une liste.")

    # Paires attendues depuis la structure
    expected_pairs: set[tuple[int, int]] = set()
    invalid_structure_entries: list[dict] = []

    for chapter_index, chapitre in enumerate(structure_data):
        if not isinstance(chapitre, dict):
            invalid_structure_entries.append({"index": chapter_index, "error": "chapter_not_object"})
            continue
        try:
            ch_num = int(chapitre.get("numero", 0))
        except (TypeError, ValueError):
            invalid_structure_entries.append({"index": chapter_index, "error": "invalid_chapter_number"})
            continue

        sections = chapitre.get("sections", [])
        if not isinstance(sections, list):
            invalid_structure_entries.append({"index": chapter_index, "chapitre": ch_num, "error": "sections_not_list"})
            continue

        for section_index, section in enumerate(sections):
            if not isinstance(section, dict):
                invalid_structure_entries.append({"index": chapter_index, "chapitre": ch_num, "section_index": section_index, "error": "section_not_object"})
                continue
            try:
                sec_num = int(section.get("numero", 0))
            except (TypeError, ValueError):
                invalid_structure_entries.append({"index": chapter_index, "chapitre": ch_num, "section_index": section_index, "error": "invalid_section_number"})
                continue
            expected_pairs.add((ch_num, sec_num))

    # Paires trouvées en BDD
    insertions_qs = FilRougeInsertion.objects.filter(livre_id=livre_id)
    found_pairs: set[tuple[int, int]] = set()
    duplicates: list[dict] = []

    for ins in insertions_qs:
        key = (ins.chapitre_numero, ins.section_numero)
        if key in found_pairs:
            duplicates.append({"chapitre": ins.chapitre_numero, "section": ins.section_numero})
        else:
            found_pairs.add(key)

    missing = [
        {"chapitre": ch, "section": sec}
        for ch, sec in sorted(expected_pairs - found_pairs)
    ]
    unexpected = [
        {"chapitre": ch, "section": sec}
        for ch, sec in sorted(found_pairs - expected_pairs)
    ]

    return {
        "ok": not missing and not duplicates and not invalid_structure_entries,
        "expected_count": len(expected_pairs),
        "found_count": len(found_pairs),
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
        "invalid_structure_entries": invalid_structure_entries,
    }
