from __future__ import annotations

from pathlib import Path
from typing import Any
from parser import read_json_file, to_int_or_raise as _to_int

BASE_DIR = Path(__file__).resolve().parent
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
FIL_ROUGE_PATH = BASE_DIR / "output" / "fil_rouge.json"
FILROUGE_PATH = BASE_DIR / "output" / "filrouge.json"

def _read_json(file_path: Path, label: str) -> Any:
	return read_json_file(file_path, label, require_non_empty=False)


def _resolve_fil_rouge_path(fil_rouge_path: Path | None) -> Path:
	if fil_rouge_path is not None:
		return fil_rouge_path
	if FIL_ROUGE_PATH.exists():
		return FIL_ROUGE_PATH
	return FILROUGE_PATH


def _normalize_fil_rouge_data(raw_data: Any) -> dict:
	if isinstance(raw_data, dict):
		insertions = raw_data.get("insertions")
		if insertions is None:
			raw_data["insertions"] = []
			return raw_data
		if not isinstance(insertions, list):
			raise ValueError("Champ 'insertions' invalide: liste attendue.")
		for item in insertions:
			if isinstance(item, dict) and item.get("contenu") is None and item.get("passage") is not None:
				item["contenu"] = item.get("passage")
		return raw_data

	if isinstance(raw_data, list):
		return {"insertions": raw_data}

	if isinstance(raw_data, str):
		try:
			decoded = json.loads(raw_data)
		except json.JSONDecodeError as exc:
			raise ValueError("Format fil rouge invalide: chaine JSON attendue.") from exc
		return _normalize_fil_rouge_data(decoded)

	raise ValueError("Format fil rouge invalide: objet, liste ou chaine attendus.")


def _collect_expected_pairs(structure_data: list[dict]) -> tuple[set[tuple[int, int]], list[dict[str, Any]]]:
	expected_pairs: set[tuple[int, int]] = set()
	invalid_structure_entries: list[dict[str, Any]] = []

	for chapter_index, chapitre in enumerate(structure_data):
		if not isinstance(chapitre, dict):
			invalid_structure_entries.append({"index": chapter_index, "error": "chapter_not_object"})
			continue

		try:
			chapitre_num = _to_int(chapitre.get("numero"), "chapitre.numero")
		except ValueError:
			invalid_structure_entries.append({"index": chapter_index, "error": "invalid_chapter_number"})
			continue

		sections = chapitre.get("sections")
		if not isinstance(sections, list):
			invalid_structure_entries.append(
				{"index": chapter_index, "chapitre": chapitre_num, "error": "sections_not_list"}
			)
			continue

		for section_index, section in enumerate(sections):
			if not isinstance(section, dict):
				invalid_structure_entries.append(
					{
						"index": chapter_index,
						"chapitre": chapitre_num,
						"section_index": section_index,
						"error": "section_not_object",
					}
				)
				continue

			try:
				section_num = _to_int(section.get("numero"), "section.numero")
			except ValueError:
				invalid_structure_entries.append(
					{
						"index": chapter_index,
						"chapitre": chapitre_num,
						"section_index": section_index,
						"error": "invalid_section_number",
					}
				)
				continue

			expected_pairs.add((chapitre_num, section_num))

	return expected_pairs, invalid_structure_entries


def verify_all_sections_have_filrouge_entry(
	structure_path: Path = STRUCTURE_PATH,
	fil_rouge_path: Path | None = None,
) -> dict[str, Any]:
	"""Verifie que chaque section de la structure a une insertion fil rouge."""
	structure_data = _read_json(structure_path, "structure des chapitres")
	if not isinstance(structure_data, list):
		raise ValueError("La structure des chapitres doit etre une liste.")

	resolved_fil_rouge_path = _resolve_fil_rouge_path(fil_rouge_path)
	fil_rouge_raw = _read_json(resolved_fil_rouge_path, "fil rouge")
	fil_rouge_data = _normalize_fil_rouge_data(fil_rouge_raw)

	expected_pairs, invalid_structure_entries = _collect_expected_pairs(structure_data)
	found_pairs: set[tuple[int, int]] = set()
	duplicates: list[dict[str, int]] = []
	invalid_entries: list[dict[str, Any]] = []

	insertions = fil_rouge_data.get("insertions", [])
	if not isinstance(insertions, list):
		raise ValueError("Champ 'insertions' invalide: liste attendue.")

	for insertion_index, insertion in enumerate(insertions):
		if not isinstance(insertion, dict):
			invalid_entries.append({"index": insertion_index, "error": "entry_not_object"})
			continue

		try:
			chapitre_num = _to_int(insertion.get("chapitre"), "insertion.chapitre")
			section_num = _to_int(insertion.get("section"), "insertion.section")
		except ValueError:
			invalid_entries.append({"index": insertion_index, "error": "invalid_chapter_or_section"})
			continue

		key = (chapitre_num, section_num)
		if key in found_pairs:
			duplicates.append({"index": insertion_index, "chapitre": chapitre_num, "section": section_num})
			continue

		found_pairs.add(key)

	missing = [
		{"chapitre": chapitre, "section": section}
		for chapitre, section in sorted(expected_pairs - found_pairs)
	]
	unexpected = [
		{"chapitre": chapitre, "section": section}
		for chapitre, section in sorted(found_pairs - expected_pairs)
	]

	return {
		"ok": not missing and not invalid_entries and not duplicates and not invalid_structure_entries,
		"structure_path": str(structure_path),
		"fil_rouge_path": str(resolved_fil_rouge_path),
		"expected_count": len(expected_pairs),
		"found_count": len(found_pairs),
		"missing": missing,
		"unexpected": unexpected,
		"duplicates": duplicates,
		"invalid_entries": invalid_entries,
		"invalid_structure_entries": invalid_structure_entries,
	}


def _print_report(report: dict[str, Any]) -> None:
	print(f"Verification fil rouge terminee: {report['found_count']}/{report['expected_count']} insertions uniques.")

	if report["missing"]:
		print("Sections sans insertion fil rouge:")
		for item in report["missing"]:
			print(f"- chapitre {item['chapitre']} section {item['section']}")

	if report["unexpected"]:
		print("Insertions non attendues:")
		for item in report["unexpected"]:
			print(f"- chapitre {item['chapitre']} section {item['section']}")

	if report["duplicates"]:
		print("Doublons d'insertion detectes:")
		for item in report["duplicates"]:
			print(f"- index {item['index']} (chapitre {item['chapitre']} section {item['section']})")

	if report["invalid_entries"]:
		print("Entrees invalides dans insertions:")
		for item in report["invalid_entries"]:
			print(f"- index {item['index']} ({item['error']})")

	if report["invalid_structure_entries"]:
		print("Entrees invalides dans structure_chapitre:")
		for item in report["invalid_structure_entries"]:
			print(f"- {item}")

	if report["ok"]:
		print("OK: toutes les sections ont une insertion fil rouge.")


if __name__ == "__main__":
	result = verify_all_sections_have_filrouge_entry()
	_print_report(result)

