"""
affichage_pdf.py — Export PDF depuis la BDD.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

from .affichage_bdd import (
    AUTHOR_PLACEHOLDER,
    BASE_DIR,
    BOOK_FORMAT_6X9_MM,
    PDF_TITLE,
    PUBLISHER_NAME,
    SIGNATURE_TEXT,
    OUTPUT_DIR,
    _extract_text,
    build_toc_entries,
    load_book_title,
    load_chapters,
    load_conclusion,
    load_intro,
    load_postface,
    load_preface,
)

OUTPUT_PDF_PATH = OUTPUT_DIR / "livre.pdf"


# ---------------------------------------------------------------------------
# BookPDF
# ---------------------------------------------------------------------------

class BookPDF(FPDF):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.header_title = PDF_TITLE
        self.book_title = PDF_TITLE
        self.current_chapter_number: str | None = None
        self.show_running_elements = True
        self.page_numbering_started = False
        self.page_number_offset = 0

    def set_header_title(self, title: Any) -> None:
        cleaned = str(title).strip() if title is not None else ""
        self.header_title = cleaned or PDF_TITLE

    def set_book_title(self, title: Any) -> None:
        cleaned = str(title).strip() if title is not None else ""
        self.book_title = cleaned or PDF_TITLE

    def set_current_chapter_number(self, chapter_number: Any | None) -> None:
        if chapter_number is None:
            self.current_chapter_number = None
            return
        cleaned = str(chapter_number).strip()
        self.current_chapter_number = cleaned or None

    def set_running_elements(self, enabled: bool) -> None:
        self.show_running_elements = enabled

    def start_page_numbering(self) -> None:
        self.page_numbering_started = True

    def set_page_number_origin_to_current(self) -> None:
        self.page_number_offset = self.page_no() - 1

    def _display_page_no(self) -> int:
        return self.page_no() - self.page_number_offset

    def header(self) -> None:
        if not self.show_running_elements:
            return
        self.set_y(10)
        self.set_font("Body", size=10)
        if self.page_no() % 2 == 1:
            header_text = self.book_title
        elif self.current_chapter_number is not None:
            header_text = f"Chapitre {self.current_chapter_number}"
        else:
            header_text = self.header_title
        self.cell(0, 8, header_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    def footer(self) -> None:
        if not self.show_running_elements or not self.page_numbering_started:
            return
        self.set_y(-12)
        self.set_font("Body", size=12)
        align = "R" if self.page_no() % 2 == 0 else "L"
        self.cell(0, 8, f"{self._display_page_no()}", align=align)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _try_add_font(pdf: FPDF, family: str, font_path: Path) -> bool:
    if not font_path.exists():
        return False
    try:
        pdf.add_font(family, style="", fname=str(font_path))
        return True
    except Exception:
        return False


def _set_unicode_font(pdf: FPDF) -> None:
    body_candidates = [
        BASE_DIR / "fonts" / "DejaVuSans.ttf",
        BASE_DIR / "fonts" / "NotoSans-Regular.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    if not any(_try_add_font(pdf, "Body", c) for c in body_candidates):
        raise FileNotFoundError("Aucune police principale trouvee. Ajoute DejaVuSans.ttf dans fonts/.")

    cjk_candidates = [
        BASE_DIR / "fonts" / "NotoSansJP-Regular.ttf",
        BASE_DIR / "fonts" / "NotoSansCJKjp-Regular.otf",
        Path("C:/Windows/Fonts/meiryo.ttc"),
        Path("C:/Windows/Fonts/msgothic.ttc"),
    ]
    fallback_families = []
    for i, c in enumerate(cjk_candidates, start=1):
        family = f"FallbackCJK{i}"
        if _try_add_font(pdf, family, c):
            fallback_families.append(family)
    if fallback_families and hasattr(pdf, "set_fallback_fonts"):
        pdf.set_fallback_fonts(fallback_families)

    pdf.set_font("Body", size=12)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _wrap_text_to_width(pdf: FPDF, text: str, max_width: float) -> list[str]:
    cleaned = _extract_text(text)
    if not cleaned:
        return [""]
    words = cleaned.split()
    lines: list[str] = []
    current = ""

    def _split_long_word(word: str) -> list[str]:
        parts: list[str] = []
        chunk = ""
        for char in word:
            candidate = chunk + char
            if chunk and pdf.get_string_width(candidate) > max_width:
                parts.append(chunk)
                chunk = char
            else:
                chunk = candidate
        if chunk:
            parts.append(chunk)
        return parts or [word]

    for word in words:
        if pdf.get_string_width(word) > max_width:
            if current:
                lines.append(current)
                current = ""
            lines.extend(_split_long_word(word))
            continue
        candidate = word if not current else f"{current} {word}"
        if pdf.get_string_width(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _insert_blank_page(pdf: BookPDF) -> None:
    state = pdf.show_running_elements
    pdf.set_running_elements(False)
    pdf.add_page()
    pdf.set_running_elements(state)


def _ensure_next_part_starts_on_even_page(pdf: BookPDF) -> None:
    if pdf.page_no() % 2 == 1:
        _insert_blank_page(pdf)


def _ensure_next_page_is_even(pdf: BookPDF) -> None:
    if pdf.page_no() % 2 == 0:
        _insert_blank_page(pdf)


def _build_pdf_instance() -> BookPDF:
    pdf = BookPDF(format=BOOK_FORMAT_6X9_MM)
    pdf.set_margins(left=20, top=30, right=20)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    _set_unicode_font(pdf)
    return pdf


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _render_sommaire(pdf: BookPDF, entries: list[tuple[str, str]], page_numbers: dict[str, int]) -> None:
    if not entries:
        return
    pdf.set_current_chapter_number(None)
    pdf.set_header_title("Sommaire")
    pdf.add_page()

    content_width = pdf.w - pdf.l_margin - pdf.r_margin
    page_col_width = 12
    title_col_width = max(10, content_width - page_col_width)

    layout_candidates = [
        (24, 10, 8, 13, 5.5), (22, 9, 6, 12, 5.1), (20, 8, 5, 11, 4.7),
        (18, 7, 4, 10, 4.3), (16, 6, 3, 9, 3.9), (14, 5, 2, 8, 3.5),
        (12, 4, 2, 7, 3.2), (11, 4, 1, 6, 2.9),
    ]

    chosen = (11, 4, 1, 6, 2.9)
    wrapped_entries: list[tuple[str, list[str]]] = []
    safety_bottom = 1.0

    for title_size, title_lh, title_gap, font_size, line_height in layout_candidates:
        pdf.set_y(24)
        pdf.set_font("Body", size=title_size)
        pdf.multi_cell(0, title_lh, "Sommaire", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.ln(title_gap)
        available = max(1.0, (pdf.h - pdf.b_margin - safety_bottom) - pdf.get_y())
        pdf.set_font("Body", size=font_size)
        candidate_wrapped = []
        total_lines = 0
        for key, title in entries:
            wrapped = _wrap_text_to_width(pdf, title, title_col_width)
            candidate_wrapped.append((key, wrapped))
            total_lines += max(1, len(wrapped))
        if total_lines * line_height <= available:
            chosen = (title_size, title_lh, title_gap, font_size, line_height)
            wrapped_entries = candidate_wrapped
            break
        wrapped_entries = candidate_wrapped

    title_size, title_lh, title_gap, font_size, line_height = chosen
    pdf.set_y(24)
    pdf.set_font("Body", size=title_size)
    pdf.multi_cell(0, title_lh, "Sommaire", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(title_gap)
    available = max(1.0, (pdf.h - pdf.b_margin - safety_bottom) - pdf.get_y())
    pdf.set_font("Body", size=font_size)

    left_col_x = pdf.l_margin
    page_col_x = pdf.l_margin + title_col_width
    row_heights = [max(1, len(w)) * line_height for _, w in wrapped_entries]
    content_height = sum(row_heights)
    gaps_count = max(0, len(wrapped_entries) - 1)
    gap_between_rows = 0.0
    top_extra = 0.0
    if content_height < available:
        extra = available - content_height
        if gaps_count > 0:
            gap_between_rows = extra / gaps_count
        else:
            top_extra = extra / 2
    pdf.set_y(pdf.get_y() + top_extra)

    for index, (key, wrapped_title) in enumerate(wrapped_entries):
        row_start_y = pdf.get_y()
        row_height = max(1, len(wrapped_title)) * line_height
        pdf.set_xy(left_col_x, row_start_y)
        pdf.multi_cell(title_col_width, line_height, "\n".join(wrapped_title), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        pdf.set_xy(page_col_x, row_start_y)
        pdf.cell(page_col_width, line_height, str(page_numbers.get(key, "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        next_y = row_start_y + row_height + (gap_between_rows if index < len(wrapped_entries) - 1 else 0)
        pdf.set_xy(left_col_x, next_y)


def _render_center_title_page(pdf: BookPDF, book_title: str) -> None:
    pdf.add_page()
    pdf.set_page_number_origin_to_current()
    pdf.set_y(pdf.h / 2 - 14)
    pdf.set_font("Body", size=30)
    pdf.multi_cell(0, 14, book_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")


def _render_title_page(pdf: BookPDF, book_title: str) -> None:
    pdf.add_page()
    pdf.set_y(20)
    pdf.set_font("Body", size=14)
    pdf.multi_cell(0, 8, AUTHOR_PLACEHOLDER, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_y(pdf.h / 2 - 14)
    pdf.set_font("Body", size=30)
    pdf.multi_cell(0, 14, book_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_y(-30)
    pdf.set_font("Body", size=14)
    pdf.cell(0, 8, PUBLISHER_NAME, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")


def _render_front_matter(pdf: BookPDF, book_title: str, toc_entries: list, page_numbers: dict) -> None:
    pdf.set_running_elements(False)
    _insert_blank_page(pdf)
    _render_center_title_page(pdf, book_title)
    _insert_blank_page(pdf)
    _render_title_page(pdf, book_title)
    _insert_blank_page(pdf)
    _render_sommaire(pdf, toc_entries, page_numbers)
    _insert_blank_page(pdf)


def _render_preface(pdf: BookPDF, preface_text: str) -> int | None:
    if not preface_text:
        return None
    pdf.set_current_chapter_number(None)
    pdf.set_header_title("Préface")
    pdf.add_page()
    start = pdf._display_page_no()
    pdf.start_page_numbering()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(0, 10, "Préface", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)
    pdf.multi_cell(0, 10, "------", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 7, preface_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.cell(0, 7, SIGNATURE_TEXT, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    return start


def _render_chapter(pdf: BookPDF, chapter_data: dict, default_number: int) -> int:
    chapter_number = _extract_text(chapter_data.get("chapitre") or default_number)
    chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"
    _ensure_next_part_starts_on_even_page(pdf)
    pdf.set_current_chapter_number(chapter_number)
    pdf.set_header_title(chapter_title)
    pdf.add_page()
    start = pdf._display_page_no()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(0, 10, f"Chapitre {chapter_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)
    pdf.multi_cell(0, 10, "------", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)
    pdf.multi_cell(0, 10, chapter_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    for section in chapter_data.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_title = _extract_text(section.get("titre"))
        if section_title:
            pdf.set_font("Body", size=16)
            pdf.multi_cell(0, 10, section_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(3)
        contenu = section.get("contenu")
        if isinstance(contenu, str) and contenu.strip():
            pdf.set_font("Body", size=12)
            pdf.multi_cell(0, 7, contenu.strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(8)
    return start


def _render_conclusion(pdf: BookPDF, conclusion_text: str) -> int | None:
    if not conclusion_text:
        return None
    _ensure_next_part_starts_on_even_page(pdf)
    pdf.set_current_chapter_number(None)
    pdf.set_header_title("Conclusion")
    pdf.add_page()
    start = pdf._display_page_no()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(0, 10, "Conclusion", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)
    pdf.multi_cell(0, 10, "------", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 7, conclusion_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return start


def _render_postface(pdf: BookPDF, postface_text: str) -> int | None:
    if not postface_text:
        return None
    _ensure_next_part_starts_on_even_page(pdf)
    pdf.set_current_chapter_number(None)
    pdf.set_header_title("Postface")
    pdf.add_page()
    start = pdf._display_page_no()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(0, 10, "Postface", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)
    pdf.multi_cell(0, 10, "------", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 7, postface_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.cell(0, 7, SIGNATURE_TEXT, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    return start


def _render_main_content(pdf: BookPDF, preface_text: str, intro: str, chapters_data: list, conclusion_text: str, postface_text: str) -> dict[str, int]:
    page_numbers: dict[str, int] = {}
    pdf.set_running_elements(True)

    preface_page = _render_preface(pdf, preface_text)
    if preface_page is not None:
        page_numbers["preface"] = preface_page
        _insert_blank_page(pdf)
        _ensure_next_page_is_even(pdf)

    pdf.set_current_chapter_number(None)
    pdf.set_header_title(PDF_TITLE)
    pdf.add_page()
    if preface_page is None:
        pdf.start_page_numbering()
    page_numbers["intro"] = pdf._display_page_no()
    pdf.set_font("Body", size=30)
    pdf.ln(20)
    pdf.multi_cell(0, 12, PDF_TITLE, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 7, intro, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for index, chapter_data in enumerate(chapters_data, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        page_numbers[f"chapter::{chapter_number}"] = _render_chapter(pdf, chapter_data, index)

    conclusion_page = _render_conclusion(pdf, conclusion_text)
    if conclusion_page is not None:
        page_numbers["conclusion"] = conclusion_page

    postface_page = _render_postface(pdf, postface_text)
    if postface_page is not None:
        page_numbers["postface"] = postface_page

    return page_numbers


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def affichage_pdf(livre_id: int) -> Path:
    book_title = load_book_title(livre_id)
    intro = load_intro(livre_id)
    conclusion_text = load_conclusion(livre_id)
    preface_text = load_preface(livre_id)
    postface_text = load_postface(livre_id)
    chapters_data = load_chapters(livre_id)

    toc_entries = build_toc_entries(
        chapters_data,
        has_preface=bool(preface_text),
        has_conclusion=bool(conclusion_text),
        has_postface=bool(postface_text),
    )

    # Passe 1 : calcul de la pagination
    probe = _build_pdf_instance()
    probe.set_book_title(book_title)
    _render_front_matter(probe, book_title, toc_entries, {})
    page_numbers = _render_main_content(probe, preface_text, intro, chapters_data, conclusion_text, postface_text)

    # Passe 2 : rendu final
    pdf = _build_pdf_instance()
    pdf.set_book_title(book_title)
    _render_front_matter(pdf, book_title, toc_entries, page_numbers)
    _render_main_content(pdf, preface_text, intro, chapters_data, conclusion_text, postface_text)

    output_path = OUTPUT_DIR / f"livre_{livre_id}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"PDF genere : {output_path}")
    return output_path
