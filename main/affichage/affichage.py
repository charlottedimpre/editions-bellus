from fpdf import FPDF, XPos, YPos
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
INTRO_PATH = BASE_DIR.parent / "introduction" / "output" / "introduction.json"
CHAPTERS_DIR = BASE_DIR.parent / "section" / "output" / "chapitre"
CONCLUSION_PATH = BASE_DIR.parent / "conclusion" / "output" / "conclusion.json"
PDF_TITLE = "Introduction"


def _set_unicode_font(pdf: FPDF) -> None:
    font_candidates = [
        BASE_DIR / "fonts" / "DejaVuSans.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]

    for font_path in font_candidates:
        if font_path.exists():
            pdf.add_font("Body", style="", fname=str(font_path))
            pdf.set_font("Body", size=12)
            return

    raise FileNotFoundError(
        "Aucune police Unicode trouvee. Ajoute DejaVuSans.ttf dans main/affichage/fonts/."
    )


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


def _load_chapter_files() -> list[Path]:
    if not CHAPTERS_DIR.exists():
        return []
    return sorted(CHAPTERS_DIR.glob("chapitre_*.json"), key=_chapter_index)


def _load_conclusion_text() -> str:
    if not CONCLUSION_PATH.exists():
        return ""
    try:
        with CONCLUSION_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ""

    if isinstance(payload, dict):
        return _extract_text(payload.get("conclusion") or payload.get("_raw"))
    return _extract_text(payload)


def _render_chapter(pdf: FPDF, chapter_data: dict[str, Any], default_number: int) -> None:
    chapter_number = _extract_text(chapter_data.get("chapitre") or default_number)
    chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"

    pdf.add_page()
    pdf.set_font("Body", size=22)
    pdf.ln(20)
    pdf.multi_cell(
        0,
        10,
        f"Chapitre {chapter_number}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(2)
    pdf.set_font("Body", size=22)
    pdf.multi_cell(
        0,
        10,
        "------",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(2)
    pdf.set_font("Body", size=22)
    pdf.multi_cell(
        0,
        10,
        chapter_title,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(20)

    for section in chapter_data.get("sections", []):
        raw_content = section.get("contenu", "")
        section_text = ""
        if isinstance(raw_content, str):
            try:
                nested_content = json.loads(raw_content)
                section_text = _extract_text(
                    nested_content.get("section_mise_a_jour")
                    or nested_content.get("contenu")
                    or nested_content.get("texte")
                    or raw_content
                )
            except json.JSONDecodeError:
                section_text = raw_content
        elif isinstance(raw_content, dict):
            section_text = _extract_text(
                raw_content.get("section_mise_a_jour")
                or raw_content.get("contenu")
                or raw_content.get("texte")
            )
        else:
            section_text = _extract_text(raw_content)


        pdf.set_font("Body", size=12)
        pdf.multi_cell(0, 8, section_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(5)


def _render_conclusion(pdf: FPDF, conclusion_text: str) -> None:
    if not conclusion_text:
        return

    pdf.add_page()
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
    pdf.multi_cell(0, 8, conclusion_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)



def affichage():
    with INTRO_PATH.open("r", encoding="utf-8") as f:
        introduction = json.load(f)
    intro = introduction.get("intro", "")
    
    

    pdf = FPDF()
    pdf.set_margins(left=20, top=25, right=20)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _set_unicode_font(pdf)
    pdf.set_font("Body", size=30)
    pdf.ln(20)
    pdf.cell(0, 12, PDF_TITLE, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)
    pdf.set_font("Body", size=12)
    pdf.multi_cell(0, 8, f"{intro}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    chapter_files = _load_chapter_files()
    for index, chapter_file in enumerate(chapter_files, start=1):
        with chapter_file.open("r", encoding="utf-8") as f:
            chapter_data = json.load(f)
        _render_chapter(pdf, chapter_data, default_number=index)

    conclusion_text = _load_conclusion_text()
    _render_conclusion(pdf, conclusion_text)



    pdf.output("test_marges.pdf")

if __name__ == "__main__":
    affichage()
