"""
affichage_md.py — Export Markdown depuis la BDD.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .affichage_bdd import (
    OUTPUT_DIR,
    PDF_TITLE,
    _extract_text,
    build_toc_entries,
    load_book_title,
    load_chapters,
    load_conclusion,
    load_intro,
    load_postface,
    load_preface,
)

OUTPUT_MD_PATH = OUTPUT_DIR / "livre.md"


def _normalize_block_text(raw_text: str) -> str:
    text = _extract_text(raw_text)
    return text.replace("\r\n", "\n").strip() if text else ""


def _slugify_heading(title: str) -> str:
    lowered = _extract_text(title).lower()
    chars: list[str] = []
    prev_dash = False
    for ch in lowered:
        if ch.isalnum():
            chars.append(ch)
            prev_dash = False
        elif not prev_dash:
            chars.append("-")
            prev_dash = True
    return "".join(chars).strip("-") or "section"


def _build_markdown(
    book_title: str,
    preface_text: str,
    intro: str,
    chapters_data: list[dict[str, Any]],
    conclusion_text: str,
    postface_text: str,
) -> str:
    toc_entries = build_toc_entries(
        chapters_data,
        has_preface=bool(preface_text),
        has_conclusion=bool(conclusion_text),
        has_postface=bool(postface_text),
    )
    lines: list[str] = []

    lines += [f"# {book_title}", "", "## Sommaire", ""]
    for _, title in toc_entries:
        lines.append(f"- [{title}](#{_slugify_heading(title)})")
    lines.append("")

    if preface_text:
        lines += ["## Préface", ""]
        preface = _normalize_block_text(preface_text)
        if preface:
            lines += [preface, "", "— Éditions Bellus", ""]

    lines += [f"## {PDF_TITLE}", ""]
    intro_text = _normalize_block_text(intro)
    if intro_text:
        lines += [intro_text, ""]

    for index, chapter_data in enumerate(chapters_data, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"
        lines += [f"## Chapitre {chapter_number} - {chapter_title}", ""]
        for section in chapter_data.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_title = _extract_text(section.get("titre"))
            if section_title:
                lines += [f"### {section_title}", ""]
            contenu = _normalize_block_text(_extract_text(section.get("contenu")))
            if contenu:
                lines += [contenu, ""]

    if conclusion_text:
        lines += ["## Conclusion", ""]
        conclusion = _normalize_block_text(conclusion_text)
        if conclusion:
            lines += [conclusion, ""]

    if postface_text:
        lines += ["## Postface", ""]
        postface = _normalize_block_text(postface_text)
        if postface:
            lines += [postface, "", "— Éditions Bellus", ""]

    return "\n".join(lines).rstrip() + "\n"


def affichage_md(livre_id: int) -> Path:
    book_title = load_book_title(livre_id)
    intro = load_intro(livre_id)
    conclusion_text = load_conclusion(livre_id)
    preface_text = load_preface(livre_id)
    postface_text = load_postface(livre_id)
    chapters_data = load_chapters(livre_id)

    markdown = _build_markdown(book_title, preface_text, intro, chapters_data, conclusion_text, postface_text)
    output_path = OUTPUT_DIR / f"livre_{livre_id}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Markdown genere : {output_path}")
    return output_path
