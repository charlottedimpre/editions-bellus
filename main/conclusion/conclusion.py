import json
import sys
from pathlib import Path

from ollama import ChatResponse, chat


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from parser import parse_conclusion, parse_resume


def load_structure():
    structure_path = BASE_DIR.parent / "structure_chapitre" / "output" / ("structure_chapitre.json")
    with structure_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_resume_mashup(chapitres: list[dict]) -> list[dict]:
    resume_dir = BASE_DIR.parent / "section" / "output" / "resume"
    mashup = []

    for chapitre in chapitres:
        ch_num = int(chapitre["numero"])
        for section in chapitre["sections"]:
            sec_num = int(section["numero"])
            coherence_path = resume_dir / f"coherence_ch{ch_num}_s{sec_num}.json"

            if not coherence_path.exists():
                mashup.append({
                    "chapitre": ch_num,
                    "section": sec_num,
                    "resume": None,
                    "missing_file": str(coherence_path),
                })
                continue

            with coherence_path.open("r", encoding="utf-8") as f:
                coherence = json.load(f)

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
    with fiche_path.open("r", encoding="utf-8") as f:
        fiche_raw = f.read()

    plan_path = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
    with plan_path.open("r", encoding="utf-8") as f:
        plan_raw = f.read()

    resume_mashup = build_resume_mashup(chapitres)

    prompt_path = BASE_DIR / "input" / "c_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': (
                f"{prompt}\n\n"
                f"FICHE DE CADRAGE :{fiche_raw}\n\n"
                f"PLAN DETAILE :{plan_raw}\n\n"
                f"RESUMES MASHUP (JSON) :{json.dumps(resume_mashup, ensure_ascii=False)}"
            ),
        },
    ])
    parsed = parse_conclusion(response.message.content)
    filepath = BASE_DIR / "output" / "conclusion.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    gen_conclu()
