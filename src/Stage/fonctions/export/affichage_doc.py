"""
affichage_doc.py — Export DOCX depuis la BDD.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZIP_DEFLATED, ZipFile

from .affichage_bdd import (
    AUTHOR_PLACEHOLDER,
    OUTPUT_DIR,
    PDF_TITLE,
    PUBLISHER_NAME,
    SIGNATURE_TEXT,
    _extract_text,
    build_toc_entries,
    load_book_title,
    load_chapters,
    load_conclusion,
    load_intro,
    load_postface,
    load_preface,
)

OUTPUT_DOCX_PATH = OUTPUT_DIR / "livre.docx"
PT = 2  # 1 point = 2 half-points Word


def _split_text_paragraphs(raw_text: str) -> list[str]:
    text = _extract_text(raw_text)
    if not text:
        return []
    return [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]


def _word_paragraph_xml(
    text: str,
    *,
    align: str = "left",
    bold: bool = False,
    size_pt: int = 12,
    space_before_twips: int = 0,
    space_after_twips: int = 120,
) -> str:
    align_map = {"left": "left", "center": "center", "right": "right", "justify": "both"}
    align_value = align_map.get(align, "left")
    ppr = f'<w:jc w:val="{align_value}"/><w:spacing w:before="{space_before_twips}" w:after="{space_after_twips}"/>'
    rpr = (
        f'<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
        f'<w:sz w:val="{max(8, size_pt) * PT}"/><w:szCs w:val="{max(8, size_pt) * PT}"/>'
        + ("<w:b/>" if bold else "")
    )
    lines = text.replace("\r\n", "\n").split("\n")
    runs: list[str] = []
    for i, line in enumerate(lines):
        safe = xml_escape(line) or " "
        runs.append(f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{safe}</w:t></w:r>')
        if i < len(lines) - 1:
            runs.append("<w:r><w:br/></w:r>")
    return f'<w:p><w:pPr>{ppr}</w:pPr>{"".join(runs)}</w:p>'


def _word_page_break_xml() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def _build_doc_blocks(
    book_title: str,
    preface_text: str,
    intro: str,
    chapters_data: list[dict[str, Any]],
    conclusion_text: str,
    postface_text: str,
) -> list[dict[str, Any]]:
    toc_entries = build_toc_entries(
        chapters_data,
        has_preface=bool(preface_text),
        has_conclusion=bool(conclusion_text),
        has_postface=bool(postface_text),
    )
    blocks: list[dict[str, Any]] = []

    # Page de titre
    blocks += [
        {"type": "paragraph", "text": AUTHOR_PLACEHOLDER, "align": "center", "size_pt": 12, "space_after": 400},
        {"type": "paragraph", "text": book_title, "align": "center", "size_pt": 28, "bold": True, "space_after": 4000},
        {"type": "paragraph", "text": PUBLISHER_NAME, "align": "center", "size_pt": 12, "space_after": 200},
    ]

    # Sommaire
    blocks.append({"type": "page_break"})
    blocks.append({"type": "paragraph", "text": "Sommaire", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
    for _, title in toc_entries:
        blocks.append({"type": "paragraph", "text": title, "align": "left", "size_pt": 12, "space_after": 90})

    # Préface
    if preface_text:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": "Préface", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
        for p in _split_text_paragraphs(preface_text):
            blocks.append({"type": "paragraph", "text": p, "align": "justify", "size_pt": 12, "space_after": 120})
        blocks.append({"type": "paragraph", "text": SIGNATURE_TEXT, "align": "right", "size_pt": 12, "space_before": 80, "space_after": 120})

    # Introduction
    blocks.append({"type": "page_break"})
    blocks.append({"type": "paragraph", "text": PDF_TITLE, "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
    for p in _split_text_paragraphs(intro):
        blocks.append({"type": "paragraph", "text": p, "align": "justify", "size_pt": 12, "space_after": 120})

    # Chapitres
    for index, chapter_data in enumerate(chapters_data, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": f"Chapitre {chapter_number}", "align": "center", "size_pt": 24, "bold": True, "space_after": 140})
        blocks.append({"type": "paragraph", "text": chapter_title, "align": "center", "size_pt": 18, "bold": True, "space_after": 260})
        for section in chapter_data.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_title = _extract_text(section.get("titre"))
            if section_title:
                blocks.append({"type": "paragraph", "text": section_title, "align": "left", "size_pt": 14, "bold": True, "space_before": 120, "space_after": 80})
            contenu = _extract_text(section.get("contenu"))
            for p in _split_text_paragraphs(contenu):
                blocks.append({"type": "paragraph", "text": p, "align": "justify", "size_pt": 12, "space_after": 120})

    # Conclusion
    if conclusion_text:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": "Conclusion", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
        for p in _split_text_paragraphs(conclusion_text):
            blocks.append({"type": "paragraph", "text": p, "align": "justify", "size_pt": 12, "space_after": 120})

    # Postface
    if postface_text:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": "Postface", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
        for p in _split_text_paragraphs(postface_text):
            blocks.append({"type": "paragraph", "text": p, "align": "justify", "size_pt": 12, "space_after": 120})
        blocks.append({"type": "paragraph", "text": SIGNATURE_TEXT, "align": "right", "size_pt": 12, "space_before": 80, "space_after": 120})

    return blocks


def _build_document_xml(blocks: list[dict[str, Any]]) -> str:
    body_parts: list[str] = []
    for block in blocks:
        if block.get("type") == "page_break":
            body_parts.append(_word_page_break_xml())
        else:
            body_parts.append(_word_paragraph_xml(
                _extract_text(block.get("text")),
                align=_extract_text(block.get("align")) or "left",
                bold=bool(block.get("bold", False)),
                size_pt=int(block.get("size_pt", 12)),
                space_before_twips=int(block.get("space_before", 0)),
                space_after_twips=int(block.get("space_after", 120)),
            ))
    sect_pr = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    ns = (
        'xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'mc:Ignorable="w14"'
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {ns}><w:body>{"".join(body_parts)}{sect_pr}</w:body></w:document>'


def _write_docx(output_path: Path, document_xml: str, title: str) -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'
    core = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{xml_escape(title)}</dc:title><dc:creator>{xml_escape(PUBLISHER_NAME)}</dc:creator><cp:lastModifiedBy>{xml_escape(PUBLISHER_NAME)}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified></cp:coreProperties>'
    app = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Microsoft Office Word</Application></Properties>'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, mode="w", compression=ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)


def affichage_doc(livre_id: int) -> Path:
    book_title = load_book_title(livre_id)
    intro = load_intro(livre_id)
    conclusion_text = load_conclusion(livre_id)
    preface_text = load_preface(livre_id)
    postface_text = load_postface(livre_id)
    chapters_data = load_chapters(livre_id)

    blocks = _build_doc_blocks(book_title, preface_text, intro, chapters_data, conclusion_text, postface_text)
    document_xml = _build_document_xml(blocks)

    output_path = OUTPUT_DIR / f"livre_{livre_id}.docx"
    _write_docx(output_path, document_xml, title=book_title)
    print(f"DOCX genere : {output_path}")
    return output_path
