import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from llm_fallback import chat_with_major_error_fallback



BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from parser import (
    parse_conclusion,
    parse_resume,
    read_json_file,
    read_text_file,
    to_int_or_raise as _to_int,
)

LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")
def _read_text(path: Path, label: str) -> str:
    return read_text_file(path, label, require_non_empty=False)


def _read_json(path: Path, label: str):
    return read_json_file(path, label, require_non_empty=False)


def load_structure():
    structure_path = BASE_DIR.parent / "structure_chapitre" / "output" / ("structure_chapitre.json")
    structure = _read_json(structure_path, "structure des chapitres")
    if not isinstance(structure, list):
        raise ValueError("La structure des chapitres doit etre une liste.")
    return structure


def build_resume_mashup(chapitres: list[dict]) -> list[dict]:
    resume_dir = BASE_DIR.parent / "section" / "output" / "resume"
    mashup = []

    for chapitre in chapitres:
        if not isinstance(chapitre, dict):
            continue

        ch_num = _to_int(chapitre.get("numero"), "chapitre.numero")
        sections = chapitre.get("sections")
        if not isinstance(sections, list):
            raise ValueError(f"chapitre.sections invalide pour chapitre {ch_num}")

        for section in sections:
            if not isinstance(section, dict):
                continue

            sec_num = _to_int(section.get("numero"), f"section.numero (chapitre {ch_num})")
            coherence_path = resume_dir / f"coherence_ch{ch_num}_s{sec_num}.json"

            if not coherence_path.exists():
                mashup.append({
                    "chapitre": ch_num,
                    "section": sec_num,
                    "resume": None,
                    "missing_file": str(coherence_path),
                })
                continue

            try:
                coherence = _read_json(coherence_path, f"resume ch{ch_num} s{sec_num}")
            except ValueError:
                mashup.append({
                    "chapitre": ch_num,
                    "section": sec_num,
                    "resume": None,
                    "invalid_json_file": str(coherence_path),
                })
                continue

            if isinstance(coherence, str):
                coherence = parse_resume(coherence, ch_num, sec_num)

            mashup.append({
                "chapitre": ch_num,
                "section": sec_num,
                "resume": coherence,
            })

    mashup.sort(key=lambda x: (x["chapitre"], x["section"]))
    return mashup


def gen_conclu():
    chapitres = load_structure()

    fiche_path = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
    fiche_raw = _read_text(fiche_path, "fiche cadrage")

    plan_path = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
    plan_raw = _read_text(plan_path, "plan detaille")

    resume_mashup = build_resume_mashup(chapitres)

    prompt_path = BASE_DIR / "input" / "c_prompt.txt"
    prompt = _read_text(prompt_path, "prompt conclusion")

    response_content = chat_with_major_error_fallback(
        ollama_model=MODEL,
        message_content=(
            f"{prompt}\n\n"
            f"FICHE DE CADRAGE :{fiche_raw}\n\n"
            f"PLAN DETAILE :{plan_raw}\n\n"
            f"RESUMES MASHUP (JSON) :{json.dumps(resume_mashup, ensure_ascii=False)}"
        ),
        context_label="conclusion",
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )

    parsed = parse_conclusion(response_content)
    if not isinstance(parsed, dict):
        raise ValueError("La conclusion parsee doit etre un objet JSON.")

    output_dir = BASE_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / "conclusion.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    return parsed


if __name__ == '__main__':
    gen_conclu()
