import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SECTION_DIR = BASE_DIR.parent / "section" / "output" / "section_fr"
SECTION_OUTPUT_DIR = BASE_DIR.parent / "section" / "output" / "section"
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
FIL_ROUGE_PATH = OUTPUT_DIR / "fil_rouge.json"

load_dotenv(ROOT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier .env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash-lite"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
CLIENT = genai.Client(api_key=GEMINI_API_KEY)


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    with STRUCTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_insertion(fil_rouge_data: dict, chapitre: int, section: int) -> str:
    for ins in fil_rouge_data.get("insertions", []):
        if int(ins.get("chapitre", -1)) == int(chapitre) and int(ins.get("section", -1)) == int(section):
            return ins.get("contenu", "")
    return ""


def _parse_model_json(content: str) -> dict:
    """Parse un JSON potentiellement encapsule dans un bloc markdown."""
    raw = (content or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("La reponse du modele doit etre un objet JSON.")
    return parsed


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


def incorporer(chapitre, section):
    prompt_path = INPUT_DIR / "mf_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_OUTPUT_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_data = json.load(f)

    with FIL_ROUGE_PATH.open("r", encoding="utf-8") as f:
        fil_rouge_data = json.load(f)

    exemple = get_insertion(fil_rouge_data, chapitre, section)

    response_text = _generate_text_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION : {section_data.get('contenu', '')}\n\n"
            f"FIL ROUGE : {exemple}\n\n"
            f"NUMERO CHAPITRE : {chapitre}\n\n"
            f"NUMERO SECTION : {section}"
        ),
        context_label=f"merge_filrouge_ch{chapitre}_s{section}",
    )

    parsed_response = _parse_model_json(response_text)
    section_data["contenu"] = (
        parsed_response.get("section_mise_a_jour")
        or parsed_response.get("contenu")
        or section_data.get("contenu", "")
    )
    return section_data


def merge_filrouge_wrapper():
    chapitres = load_structure()
    for chapitre in chapitres:
        chapitre_num = int(chapitre["numero"])
        for section in chapitre.get("sections", []):
            section_num = int(section["numero"])
            result = incorporer(chapitre_num, section_num)
            print(f"Résultat pour Chapitre {chapitre_num} Section {section_num}\n{'-' * 80}")

            filepath = SECTION_DIR / f"section_ch{chapitre_num}_s{section_num}.json"
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    merge_filrouge_wrapper()