import json
import sys
from pathlib import Path

from ollama import ChatResponse, chat

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from parser import parse_filrouge, parse_resume


def load_structure() -> list[dict]:
    structure_path = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
    with structure_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Fichier introuvable pour {label}: {path}") from exc


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

            try:
                coherence = json.loads(_read_text(coherence_path, "resume de coherence"))
            except json.JSONDecodeError:
                coherence = _read_text(coherence_path, "resume de coherence")

            if isinstance(coherence, str):
                coherence = parse_resume(coherence, ch_num, sec_num)

            mashup.append({
                "chapitre": ch_num,
                "section": sec_num,
                "resume": coherence,
            })

    mashup.sort(key=lambda x: (x["chapitre"], x["section"]))
    return mashup


def gen_filrouge():
    chapitres = load_structure()

    fiche_path = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
    fiche_raw = _read_text(fiche_path, "fiche de cadrage")

    plan_path = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
    plan_raw = _read_text(plan_path, "plan detaille")

    resume_mashup = build_resume_mashup(chapitres)

    prompt_path = BASE_DIR / "input" / "fr_prompt.txt"
    prompt = _read_text(prompt_path, "prompt fil rouge")

    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': (
                f"{prompt}\n\n"
                f"FICHE DE CADRAGE :{fiche_raw}\n\n"
                f"PLAN DETAILLE :{plan_raw}\n\n"
                f"RESUMES MASHUP (JSON) :{json.dumps(resume_mashup, ensure_ascii=False)}"
            ),
        },
    ])

    parsed = parse_filrouge(response.message.content)
    filepath = BASE_DIR / "output" / "fil_rouge.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    gen_filrouge()
