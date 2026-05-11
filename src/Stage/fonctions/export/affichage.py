from fpdf import FPDF, XPos, YPos
import json
from pathlib import Path
from typing import Any

from ..introduction import recup_intro
from ..conclusion import recup_conclusion
from ..fiche_cadrage import recup_fiche_cadrage
from ..sections.section import recup_section_texte_all

BASE_DIR = Path(__file__).resolve().parent
#INTRO_PATH = BASE_DIR.parent / "introduction" / "output" / "introduction.json"
#CHAPTERS_DIR = BASE_DIR.parent / "section" / "output" / "chapitre"
#CONCLUSION_PATH = BASE_DIR.parent / "conclusion" / "output" / "conclusion.json"
#FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PDF_TITLE = "Introduction"
OUTPUT_PDF_PATH = BASE_DIR / "output" / "livre.pdf"
AUTHOR_PLACEHOLDER = "Lise Genest"
PUBLISHER_NAME = "Editions Bellus"
BOOK_FORMAT_6X9_MM = (152.4, 228.6)


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
        if title is None:
            self.header_title = PDF_TITLE
            return
        cleaned_title = str(title).strip()
        self.header_title = cleaned_title or PDF_TITLE

    def set_book_title(self, title: Any) -> None:
        if title is None:
            self.book_title = PDF_TITLE
            return
        cleaned_title = str(title).strip()
        self.book_title = cleaned_title or PDF_TITLE

    def set_current_chapter_number(self, chapter_number: Any | None) -> None:
        if chapter_number is None:
            self.current_chapter_number = None
            return
        cleaned = str(chapter_number).strip()
        self.current_chapter_number = cleaned or None

    def set_running_elements(self, enabled: bool) -> None:
        self.show_running_elements = enabled

    def start_page_numbering(self) -> None:
        # Active l'affichage de la pagination a partir de ce point du livre.
        self.page_numbering_started = True

    def set_page_number_origin_to_current(self) -> None:
        # La page courante devient 1 dans le comptage logique.
        self.page_number_offset = self.page_no() - 1

    def _display_page_no(self) -> int:
        return self.page_no() - self.page_number_offset

    def header(self) -> None:
        if not self.show_running_elements:
            return
        # En-tete type livre: impair=titre, pair=chapitre courant.
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
        if not self.show_running_elements:
            return
        if not self.page_numbering_started:
            return
        # Pied de page en marge exterieure (livre): impair a droite, pair a gauche.
        self.set_y(-12)
        self.set_font("Body", size=12)
        display_no = self._display_page_no()
        align = "R" if self.page_no() % 2 == 0 else "L"
        self.cell(0, 8, f"{display_no}", align=align)


def _try_add_font(pdf: FPDF, family: str, font_path: Path) -> bool:
    if not font_path.exists():
        return False
    try:
        pdf.add_font(family, style="", fname=str(font_path))
        return True
    except Exception:
        return False


def _set_unicode_font(pdf: FPDF) -> None:
    # Police principale pour le corps (latin).
    body_candidates = [
        BASE_DIR / "fonts" / "DejaVuSans.ttf",
        BASE_DIR / "fonts" / "NotoSans-Regular.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]

    body_font_ok = any(_try_add_font(pdf, "Body", candidate) for candidate in body_candidates)
    if not body_font_ok:
        raise FileNotFoundError(
            "Aucune police principale trouvee. Ajoute DejaVuSans.ttf dans main/affichage/fonts/."
        )

    # Polices de fallback pour les caracteres CJK (dont japonais).
    cjk_candidates = [
        BASE_DIR / "fonts" / "NotoSansJP-Regular.ttf",
        BASE_DIR / "fonts" / "NotoSansCJKjp-Regular.otf",
        Path("C:/Windows/Fonts/meiryo.ttc"),
        Path("C:/Windows/Fonts/msgothic.ttc"),
        Path("C:/Windows/Fonts/YuGothR.ttc"),
        Path("C:/Windows/Fonts/YuGothM.ttc"),
    ]
    fallback_families: list[str] = []
    for index, candidate in enumerate(cjk_candidates, start=1):
        family = f"FallbackCJK{index}"
        if _try_add_font(pdf, family, candidate):
            fallback_families.append(family)

    if fallback_families and hasattr(pdf, "set_fallback_fonts"):
        pdf.set_fallback_fonts(fallback_families)

    pdf.set_font("Body", size=12)


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _chapter_index(path: Path) -> int:
    try:
        return int(path.stem.split("_")[-1])
    except ValueError:
        return 10**9


def _load_chapter_files() -> list[dict]:
    sections = recup_section_texte_all()

    chapitres = {}

    for s in sections:
        chap_num = s["chapitre"]

        if chap_num not in chapitres:
            chapitres[chap_num] = {
                "chapitre": chap_num,
                "titre": s.get("titre_chapitre"),
                "sections": []
            }

        chapitres[chap_num]["sections"].append({
            "titre": s.get("titre_section"),
            "contenu": s.get("contenu")
        })

    return sorted(
        chapitres.values(),
        key=lambda x: x["chapitre"]
    )


def _load_json_file(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _load_conclusion_text() -> str:
    payload = json.loads(recup_conclusion())

    if isinstance(payload, dict):
        return _extract_text(payload.get("conclusion") or payload.get("_raw"))
    return _extract_text(payload)


def _extract_tag_content(raw_text: str, tag_name: str) -> str:
    start_tag = f"<{tag_name}>"
    end_tag = f"</{tag_name}>"
    start_idx = raw_text.find(start_tag)
    if start_idx == -1:
        return ""
    start_idx += len(start_tag)
    end_idx = raw_text.find(end_tag, start_idx)
    if end_idx == -1:
        return ""
    return raw_text[start_idx:end_idx].strip()


def _find_first_key_text(payload: Any, target_key: str) -> str:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == target_key:
                text = _extract_text(value)
                if text:
                    return text
            nested = _find_first_key_text(value, target_key)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _find_first_key_text(item, target_key)
            if nested:
                return nested
    return ""


def _load_book_title() -> str:
    payload = json.loads(recup_fiche_cadrage())
    if not payload:
        return PDF_TITLE

    sujet = _find_first_key_text(payload, "titre_saisi_utilisateur")
    if sujet:
        return sujet

    if isinstance(payload, dict):
        raw_value = _extract_text(payload.get("_raw"))
        if raw_value:
            raw_sujet = _extract_tag_content(raw_value, "titre_saisi_utilisateur")
            if raw_sujet:
                return raw_sujet

    return PDF_TITLE


def _insert_blank_page(pdf: BookPDF) -> None:
    running_elements_state = pdf.show_running_elements
    pdf.set_running_elements(False)
    pdf.add_page()
    pdf.set_running_elements(running_elements_state)


def _ensure_next_part_starts_on_even_page(pdf: BookPDF) -> None:
    if pdf.page_no() % 2 == 1:
        _insert_blank_page(pdf)


def _extract_section_text(raw_content: Any, max_depth: int = 6) -> str:
    if max_depth <= 0:
        return _extract_text(raw_content)

    if isinstance(raw_content, dict):
        # Priorite aux cles metier.
        for key in ("section_mise_a_jour", "contenu", "texte"):
            if key in raw_content:
                candidate = _extract_section_text(raw_content.get(key), max_depth=max_depth - 1)
                if candidate:
                    return candidate

        # Fallback sur les valeurs imbriquees.
        for value in raw_content.values():
            candidate = _extract_section_text(value, max_depth=max_depth - 1)
            if candidate:
                return candidate
        return ""

    if isinstance(raw_content, (list, tuple)):
        parts = [_extract_section_text(item, max_depth=max_depth - 1) for item in raw_content]
        non_empty_parts = [part for part in parts if part]
        return "\n\n".join(non_empty_parts)

    if isinstance(raw_content, str):
        cleaned = raw_content.strip()
        if not cleaned:
            return ""

        # Parse uniquement les chaines qui ressemblent a du JSON.
        if cleaned[0] in "{[\"":
            try:
                decoded = json.loads(cleaned)
            except json.JSONDecodeError:
                return cleaned
            return _extract_section_text(decoded, max_depth=max_depth - 1) or cleaned

        return cleaned

    return _extract_text(raw_content)


def _extract_sections_contents(chapter_data: dict[str, Any]) -> list[str]:
    sections = chapter_data.get("sections")
    if not isinstance(sections, list):
        return []

    contents: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        contenu = section.get("contenu")
        if isinstance(contenu, str) and contenu.strip():
            contents.append(contenu.strip())

    return contents


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


def _build_toc_entries(chapters: list[dict[str, Any]], has_conclusion: bool) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = [("intro", "Introduction")]
    for index, chapter_data in enumerate(chapters, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"
        entries.append((f"chapter::{chapter_number}", f"Chapitre {chapter_number} - {chapter_title}"))
    if has_conclusion:
        entries.append(("conclusion", "Conclusion"))
    return entries


def _render_chapter(pdf: BookPDF, chapter_data: dict[str, Any], default_number: int) -> int:
    chapter_number = _extract_text(chapter_data.get("chapitre") or default_number)
    chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"

    _ensure_next_part_starts_on_even_page(pdf)
    pdf.set_current_chapter_number(chapter_number)
    pdf.set_header_title(chapter_title)
    pdf.add_page()
    start_page_no = pdf._display_page_no()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(
        0, 10,
        f"Chapitre {chapter_number}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.ln(2)
    pdf.set_font("Body", size=22)
    pdf.multi_cell(
        0, 10, "------",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.ln(2)
    pdf.set_font("Body", size=22)
    pdf.multi_cell(
        0, 10, chapter_title,
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.ln(20)

    sections = chapter_data.get("sections", [])
    for section in sections:
        if not isinstance(section, dict):
            continue

        # Titre de section
        section_title = _extract_text(section.get("titre"))
        if section_title:
            pdf.set_font("Body", size=16)
            pdf.multi_cell(0, 10, section_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(3)

        # Contenu de section
        contenu = section.get("contenu")
        if isinstance(contenu, str) and contenu.strip():
            pdf.set_font("Body", size=12)
            pdf.multi_cell(0, 7, contenu.strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(8)
    return start_page_no


def _render_conclusion(pdf: BookPDF, conclusion_text: str) -> int | None:
    if not conclusion_text:
        return None

    _ensure_next_part_starts_on_even_page(pdf)
    pdf.set_current_chapter_number(None)
    pdf.set_header_title("Conclusion")
    pdf.add_page()
    start_page_no = pdf._display_page_no()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(
        0,
        10,
        "Conclusion",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(2)
    pdf.multi_cell(
        0,
        10,
        "------",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(20)

    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 7, conclusion_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return start_page_no


def _render_sommaire(pdf: BookPDF, entries: list[tuple[str, str]], page_numbers: dict[str, int]) -> None:
    if not entries:
        return

    pdf.set_current_chapter_number(None)
    pdf.set_header_title("Sommaire")
    pdf.add_page()

    content_width = pdf.w - pdf.l_margin - pdf.r_margin
    page_col_width = 12
    title_col_width = max(10, content_width - page_col_width)

    # Combinaisons du titre + texte du sommaire, de la plus lisible a la plus compacte.
    layout_candidates = [
        (24, 10, 8, 13, 5.5),
        (22, 9, 6, 12, 5.1),
        (20, 8, 5, 11, 4.7),
        (18, 7, 4, 10, 4.3),
        (16, 6, 3, 9, 3.9),
        (14, 5, 2, 8, 3.5),
        (12, 4, 2, 7, 3.2),
        (11, 4, 1, 6, 2.9),
    ]

    chosen_title_size = 11
    chosen_title_line_height = 4
    chosen_title_gap = 1
    chosen_font_size = 6
    chosen_line_height = 2.9
    wrapped_entries: list[tuple[str, list[str]]] = []

    safety_bottom = 1.0
    for title_size, title_line_height, title_gap, font_size, line_height in layout_candidates:
        pdf.set_y(24)
        pdf.set_font("Body", size=title_size)
        pdf.multi_cell(0, title_line_height, "Sommaire", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.ln(title_gap)

        available_height = max(1.0, (pdf.h - pdf.b_margin - safety_bottom) - pdf.get_y())
        pdf.set_font("Body", size=font_size)

        candidate_wrapped_entries: list[tuple[str, list[str]]] = []
        total_lines = 0
        for key, title in entries:
            wrapped_title = _wrap_text_to_width(pdf, title, title_col_width)
            candidate_wrapped_entries.append((key, wrapped_title))
            total_lines += max(1, len(wrapped_title))

        required_height = total_lines * line_height
        if required_height <= available_height:
            chosen_title_size = title_size
            chosen_title_line_height = title_line_height
            chosen_title_gap = title_gap
            chosen_font_size = font_size
            chosen_line_height = line_height
            wrapped_entries = candidate_wrapped_entries
            break

        wrapped_entries = candidate_wrapped_entries

    # Rendu final avec le layout retenu.
    pdf.set_y(24)
    pdf.set_font("Body", size=chosen_title_size)
    pdf.multi_cell(
        0,
        chosen_title_line_height,
        "Sommaire",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(chosen_title_gap)

    available_height = max(1.0, (pdf.h - pdf.b_margin - safety_bottom) - pdf.get_y())
    pdf.set_font("Body", size=chosen_font_size)

    left_col_x = pdf.l_margin
    page_col_x = pdf.l_margin + title_col_width

    row_heights = [
        max(1, len(wrapped_title)) * chosen_line_height for _, wrapped_title in wrapped_entries
    ]
    content_height = sum(row_heights)
    gaps_count = max(0, len(wrapped_entries) - 1)

    # Etale les entrees pour occuper toute la page disponible.
    gap_between_rows = 0.0
    top_extra_offset = 0.0
    if content_height < available_height:
        extra_space = available_height - content_height
        if gaps_count > 0:
            gap_between_rows = extra_space / gaps_count
        else:
            top_extra_offset = extra_space / 2

    pdf.set_y(pdf.get_y() + top_extra_offset)

    for index, (key, wrapped_title) in enumerate(wrapped_entries):
        page_text = str(page_numbers.get(key, ""))
        row_start_y = pdf.get_y()
        row_height = max(1, len(wrapped_title)) * chosen_line_height

        pdf.set_xy(left_col_x, row_start_y)
        pdf.multi_cell(
            title_col_width,
            chosen_line_height,
            "\n".join(wrapped_title),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="L",
        )

        # Numero de page en face de la premiere ligne du titre.
        pdf.set_xy(page_col_x, row_start_y)
        pdf.cell(
            page_col_width,
            chosen_line_height,
            page_text,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="R",
        )

        next_y = row_start_y + row_height
        if index < len(wrapped_entries) - 1:
            next_y += gap_between_rows
        pdf.set_xy(left_col_x, next_y)


def _render_center_title_page(pdf: BookPDF, book_title: str) -> None:
    pdf.add_page()
    pdf.set_page_number_origin_to_current()
    # Titre seul centre verticalement.
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


def _build_pdf_instance() -> BookPDF:
    pdf = BookPDF(format=BOOK_FORMAT_6X9_MM)
    pdf.set_margins(left=20, top=30, right=20)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    _set_unicode_font(pdf)
    return pdf


def _render_front_matter(
    pdf: BookPDF,
    book_title: str,
    toc_entries: list[tuple[str, str]],
    page_numbers: dict[str, int],
) -> None:
    pdf.set_running_elements(False)
    _insert_blank_page(pdf)
    _render_center_title_page(pdf, book_title)
    _insert_blank_page(pdf)
    _render_title_page(pdf, book_title)
    _insert_blank_page(pdf)
    _render_sommaire(pdf, toc_entries, page_numbers)
    _insert_blank_page(pdf)


def _render_main_content(
    pdf: BookPDF,
    intro: str,
    chapters_data: list[dict[str, Any]],
    conclusion_text: str,
) -> dict[str, int]:
    page_numbers: dict[str, int] = {}

    pdf.set_running_elements(True)
    pdf.set_current_chapter_number(None)
    pdf.set_header_title(PDF_TITLE)
    pdf.add_page()
    pdf.start_page_numbering()
    page_numbers["intro"] = pdf._display_page_no()

    pdf.set_font("Body", size=30)
    pdf.ln(20)
    pdf.multi_cell(0, 12, PDF_TITLE, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 7, f"{intro}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for index, chapter_data in enumerate(chapters_data, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        page_numbers[f"chapter::{chapter_number}"] = _render_chapter(
            pdf, chapter_data, default_number=index
        )

    conclusion_page = _render_conclusion(pdf, conclusion_text)
    if conclusion_page is not None:
        page_numbers["conclusion"] = conclusion_page

    return page_numbers



def affichage():
    introduction = json.loads(recup_intro())
    intro = introduction.get("intro", "")
    book_title = _load_book_title()

    chapters_data: list[dict[str, Any]] = _load_chapter_files()
    conclusion_text = _load_conclusion_text()
    toc_entries = _build_toc_entries(chapters_data, has_conclusion=bool(conclusion_text))

    pagination_probe_pdf = _build_pdf_instance()
    pagination_probe_pdf.set_book_title(book_title)
    _render_front_matter(pagination_probe_pdf, book_title, toc_entries, page_numbers={})
    page_numbers = _render_main_content(
        pagination_probe_pdf,
        intro,
        chapters_data,
        conclusion_text,
    )

    pdf = _build_pdf_instance()
    pdf.set_book_title(book_title)
    _render_front_matter(pdf, book_title, toc_entries, page_numbers)
    _render_main_content(pdf, intro, chapters_data, conclusion_text)

    OUTPUT_PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT_PDF_PATH))

if __name__ == "__main__":
    affichage()
