from __future__ import annotations

from typing import Any

from affichage import (
    BASE_DIR,
    INTRO_PATH,
    PDF_TITLE,
    _build_toc_entries,
    _extract_text,
    _load_book_title,
    _load_chapter_files,
    _load_conclusion_text,
    _load_json_file,
    _load_postface_text,
    _load_preface_text,
)

OUTPUT_MD_PATH = BASE_DIR / "output" / "livre.md"


def _normalize_block_text(raw_text: str) -> str:
    text = _extract_text(raw_text)
    if not text:
        return ""
    return text.replace("\r\n", "\n").strip()


def _slugify_heading(title: str) -> str:
    lowered = _extract_text(title).lower()
    cleaned_chars: list[str] = []
    previous_dash = False
    for ch in lowered:
        if ch.isalnum():
            cleaned_chars.append(ch)
            previous_dash = False
            continue
        if not previous_dash:
            cleaned_chars.append("-")
            previous_dash = True
    return "".join(cleaned_chars).strip("-") or "section"


def _build_markdown(
    book_title: str,
    preface_text: str,
    intro: str,
    chapters_data: list[dict[str, Any]],
    conclusion_text: str,
    postface_text: str,
) -> str:
    toc_entries = _build_toc_entries(
        chapters_data,
        has_preface=bool(preface_text),
        has_conclusion=bool(conclusion_text),
        has_postface=bool(postface_text),
    )
    lines: list[str] = []

    lines.append(f"# {book_title}")
    lines.append("")
    lines.append("## Sommaire")
    lines.append("")

    for _, title in toc_entries:
        anchor = _slugify_heading(title)
        lines.append(f"- [{title}](#{anchor})")

    lines.append("")

    if preface_text:
        lines.append("## Préface")
        lines.append("")
        preface = _normalize_block_text(preface_text)
        if preface:
            lines.append(preface)
            lines.append("")
            lines.append("— Éditions Bellus")
            lines.append("")

    lines.append(f"## {PDF_TITLE}")
    lines.append("")
    intro_text = _normalize_block_text(intro)
    if intro_text:
        lines.append(intro_text)
        lines.append("")

    for index, chapter_data in enumerate(chapters_data, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"
        chapter_heading = f"Chapitre {chapter_number} - {chapter_title}"

        lines.append(f"## {chapter_heading}")
        lines.append("")

        for section in chapter_data.get("sections", []):
            if not isinstance(section, dict):
                continue

            section_title = _extract_text(section.get("titre"))
            if section_title:
                lines.append(f"### {section_title}")
                lines.append("")

            contenu = _normalize_block_text(_extract_text(section.get("contenu")))
            if contenu:
                lines.append(contenu)
                lines.append("")

    if conclusion_text:
        lines.append("## Conclusion")
        lines.append("")
        conclusion = _normalize_block_text(conclusion_text)
        if conclusion:
            lines.append(conclusion)
            lines.append("")

    if postface_text:
        lines.append("## Postface")
        lines.append("")
        postface = _normalize_block_text(postface_text)
        if postface:
            lines.append(postface)
            lines.append("")
            lines.append("— Éditions Bellus")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def affichage_md() -> None:
    introduction = _load_json_file(INTRO_PATH, default={})
    intro = _extract_text(introduction.get("intro", "")) if isinstance(introduction, dict) else ""
    book_title = _load_book_title()

    chapter_files = _load_chapter_files()
    chapters_data: list[dict[str, Any]] = []
    for chapter_file in chapter_files:
        chapter_payload = _load_json_file(chapter_file, default={})
        if isinstance(chapter_payload, dict):
            chapters_data.append(chapter_payload)

    conclusion_text = _load_conclusion_text()
    postface_text = _load_postface_text()
    preface_text = _load_preface_text()

    markdown = _build_markdown(book_title, preface_text, intro, chapters_data, conclusion_text, postface_text)
    OUTPUT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD_PATH.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    affichage_md()
