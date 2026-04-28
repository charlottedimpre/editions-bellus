from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZIP_DEFLATED, ZipFile

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

OUTPUT_DOCX_PATH = BASE_DIR / "output" / "livre.docx"
AUTHOR_PLACEHOLDER = "[AUTEUR]"
PUBLISHER_NAME = "Editions Bellus"
SIGNATURE_TEXT = "— Éditions Bellus"

# Unites Word: 1 point = 2 half-points.
PT = 2


def _split_text_paragraphs(raw_text: str) -> list[str]:
    text = _extract_text(raw_text)
    if not text:
        return []
    normalized = text.replace("\r\n", "\n")
    return [part.strip() for part in normalized.split("\n\n") if part.strip()]


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

    ppr_parts = [
        f'<w:jc w:val="{align_value}"/>',
        f'<w:spacing w:before="{space_before_twips}" w:after="{space_after_twips}"/>',
    ]
    rpr_parts = [
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>',
        f'<w:sz w:val="{max(8, size_pt) * PT}"/>',
        f'<w:szCs w:val="{max(8, size_pt) * PT}"/>',
    ]
    if bold:
        rpr_parts.append("<w:b/>")

    lines = text.replace("\r\n", "\n").split("\n")
    run_xml: list[str] = []
    for index, line in enumerate(lines):
        safe_line = xml_escape(line)
        if not safe_line:
            safe_line = " "
        run_xml.append(f'<w:r><w:rPr>{"".join(rpr_parts)}</w:rPr><w:t xml:space="preserve">{safe_line}</w:t></w:r>')
        if index < len(lines) - 1:
            run_xml.append("<w:r><w:br/></w:r>")

    return f'<w:p><w:pPr>{"".join(ppr_parts)}</w:pPr>{"".join(run_xml)}</w:p>'


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
    toc_entries = _build_toc_entries(
        chapters_data,
        has_preface=bool(preface_text),
        has_conclusion=bool(conclusion_text),
        has_postface=bool(postface_text),
    )

    blocks: list[dict[str, Any]] = []

    blocks.append({"type": "paragraph", "text": AUTHOR_PLACEHOLDER, "align": "center", "size_pt": 12, "space_after": 400})
    blocks.append({"type": "paragraph", "text": book_title, "align": "center", "size_pt": 28, "bold": True, "space_after": 4000})
    blocks.append({"type": "paragraph", "text": PUBLISHER_NAME, "align": "center", "size_pt": 12, "space_after": 200})

    blocks.append({"type": "page_break"})
    blocks.append({"type": "paragraph", "text": "Sommaire", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
    for _, title in toc_entries:
        blocks.append({"type": "paragraph", "text": title, "align": "left", "size_pt": 12, "space_after": 90})

    if preface_text:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": "Préface", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
        for paragraph in _split_text_paragraphs(preface_text):
            blocks.append({"type": "paragraph", "text": paragraph, "align": "justify", "size_pt": 12, "space_after": 120})
        blocks.append({"type": "paragraph", "text": SIGNATURE_TEXT, "align": "right", "size_pt": 12, "space_before": 80, "space_after": 120})

    blocks.append({"type": "page_break"})
    blocks.append({"type": "paragraph", "text": PDF_TITLE, "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
    for paragraph in _split_text_paragraphs(intro):
        blocks.append({"type": "paragraph", "text": paragraph, "align": "justify", "size_pt": 12, "space_after": 120})

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
            if contenu:
                for paragraph in _split_text_paragraphs(contenu):
                    blocks.append({"type": "paragraph", "text": paragraph, "align": "justify", "size_pt": 12, "space_after": 120})

    if conclusion_text:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": "Conclusion", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
        for paragraph in _split_text_paragraphs(conclusion_text):
            blocks.append({"type": "paragraph", "text": paragraph, "align": "justify", "size_pt": 12, "space_after": 120})

    if postface_text:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "paragraph", "text": "Postface", "align": "center", "size_pt": 24, "bold": True, "space_after": 260})
        for paragraph in _split_text_paragraphs(postface_text):
            blocks.append({"type": "paragraph", "text": paragraph, "align": "justify", "size_pt": 12, "space_after": 120})
        blocks.append({"type": "paragraph", "text": SIGNATURE_TEXT, "align": "right", "size_pt": 12, "space_before": 80, "space_after": 120})

    return blocks


def _build_document_xml(blocks: list[dict[str, Any]]) -> str:
    body_parts: list[str] = []
    for block in blocks:
        if block.get("type") == "page_break":
            body_parts.append(_word_page_break_xml())
            continue
        body_parts.append(
            _word_paragraph_xml(
                _extract_text(block.get("text")),
                align=_extract_text(block.get("align")) or "left",
                bold=bool(block.get("bold", False)),
                size_pt=int(block.get("size_pt", 12)),
                space_before_twips=int(block.get("space_before", 0)),
                space_after_twips=int(block.get("space_after", 120)),
            )
        )

    sect_pr = (
        '<w:sectPr>'
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/>'
        '</w:sectPr>'
    )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
        'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
        'mc:Ignorable="w14 wp14">'
        f'<w:body>{"".join(body_parts)}{sect_pr}</w:body>'
        '</w:document>'
    )


def _write_docx(output_path: Path, document_xml: str, title: str) -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content_types_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
  <Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>
  <Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>
</Types>
"""
    rels_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>
  <Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>
</Relationships>
"""
    core_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">
  <dc:title>{xml_escape(title)}</dc:title>
  <dc:creator>{xml_escape(PUBLISHER_NAME)}</dc:creator>
  <cp:lastModifiedBy>{xml_escape(PUBLISHER_NAME)}</cp:lastModifiedBy>
  <dcterms:created xsi:type=\"dcterms:W3CDTF\">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now_iso}</dcterms:modified>
</cp:coreProperties>
"""
    app_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">
  <Application>Microsoft Office Word</Application>
</Properties>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, mode="w", compression=ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("_rels/.rels", rels_xml)
        docx_zip.writestr("word/document.xml", document_xml)
        docx_zip.writestr("docProps/core.xml", core_xml)
        docx_zip.writestr("docProps/app.xml", app_xml)


def affichage_doc() -> None:
    introduction = _load_json_file(INTRO_PATH, default={})
    intro = _extract_text(introduction.get("intro", "")) if isinstance(introduction, dict) else ""
    book_title = _load_book_title()

    chapter_files = _load_chapter_files()
    chapters_data: list[dict] = []
    for chapter_file in chapter_files:
        chapter_payload = _load_json_file(chapter_file, default={})
        if isinstance(chapter_payload, dict):
            chapters_data.append(chapter_payload)

    conclusion_text = _load_conclusion_text()
    postface_text = _load_postface_text()
    preface_text = _load_preface_text()

    blocks = _build_doc_blocks(book_title, preface_text, intro, chapters_data, conclusion_text, postface_text)
    document_xml = _build_document_xml(blocks)
    _write_docx(OUTPUT_DOCX_PATH, document_xml, title=book_title)


if __name__ == "__main__":
    affichage_doc()

