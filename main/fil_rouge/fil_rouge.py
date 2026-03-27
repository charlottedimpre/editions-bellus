import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from parser import parse_filrouge, parse_resume

load_dotenv(ROOT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier .env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash-lite"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
CLIENT = genai.Client(api_key=GEMINI_API_KEY)


def _generate_text_with_retry(contents: str, context_label: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
            )
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError(f"Reponse vide de Gemini ({context_label}).")
            return text
        except ServerError as err:
            status_code = getattr(err, "status_code", None)
            is_503 = status_code == 503 or str(err).startswith("503")
            if not is_503:
                raise RuntimeError(f"Erreur serveur Gemini non 503 ({context_label}): {err}") from err

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Erreur 503 Gemini apres {MAX_RETRIES} tentatives ({context_label})."
                ) from err

            print(
                f"Gemini indisponible (503) [{context_label}] tentative {attempt}/{MAX_RETRIES}, nouvelle tentative dans {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Echec de generation Gemini ({context_label}).")


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

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"FICHE DE CADRAGE :{fiche_raw}\n\n"
            f"PLAN DETAILLE :{plan_raw}\n\n"
            f"RESUMES MASHUP (JSON) :{json.dumps(resume_mashup, ensure_ascii=False)}"
        ),
        context_label="fil_rouge",
    )

    parsed = parse_filrouge(response_text)
    filepath = BASE_DIR / "output" / "fil_rouge.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    gen_filrouge()
