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
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SECTION_DIR = BASE_DIR.parent / "section" / "output" / "section_fr"
SECTION_OUTPUT_DIR = BASE_DIR.parent / "section" / "output" / "section"
STRUCTURE_PATH = BASE_DIR.parent / "structure_chapitre" / "output" / "structure_chapitre.json"
FIL_ROUGE_PATH = OUTPUT_DIR / "fil_rouge.json"

from parser import parse_filrouge

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


def _normalize_fil_rouge_data(raw_data) -> dict:
    if isinstance(raw_data, dict):
        insertions = raw_data.get("insertions", [])
        if isinstance(insertions, list):
            for item in insertions:
                if isinstance(item, dict) and item.get("contenu") is None and item.get("passage") is not None:
                    item["contenu"] = item.get("passage")
        return raw_data

    if isinstance(raw_data, list):
        normalized = parse_filrouge(json.dumps(raw_data, ensure_ascii=False))
        if normalized.get("insertions"):
            return normalized

    if isinstance(raw_data, str):
        text_value = raw_data
        # Compatibilite historique: certains fichiers contiennent une chaine JSON encodee.
        try:
            decoded = json.loads(raw_data)
            if isinstance(decoded, dict):
                return _normalize_fil_rouge_data(decoded)
            if isinstance(decoded, list):
                return _normalize_fil_rouge_data(decoded)
            if isinstance(decoded, str):
                text_value = decoded
        except (json.JSONDecodeError, TypeError):
            pass
        return parse_filrouge(text_value)

    raise ValueError("Format fil_rouge.json invalide: dict ou str attendu.")


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


def _generate_json_with_retry(contents: str, context_label: str) -> dict:
    """Genere puis parse un JSON, avec retries sur JSONDecodeError."""
    for attempt in range(1, MAX_RETRIES + 1):
        response_text = _generate_text_with_retry(contents=contents, context_label=context_label)
        try:
            return _parse_model_json(response_text)
        except json.JSONDecodeError as err:
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"JSON invalide apres {MAX_RETRIES} tentatives ({context_label}): {err}"
                ) from err

            print(
                f"JSON invalide [{context_label}] tentative {attempt}/{MAX_RETRIES}, nouvelle tentative dans {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Echec de parsing JSON ({context_label}).")


def incorporer(chapitre, section):
    prompt_path = INPUT_DIR / "mf_prompt.txt"
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    section_path = SECTION_OUTPUT_DIR / f"section_ch{chapitre}_s{section}.json"
    with section_path.open("r", encoding="utf-8") as f:
        section_data = json.load(f)

    with FIL_ROUGE_PATH.open("r", encoding="utf-8") as f:
        fil_rouge_data = json.load(f)
    fil_rouge_data = _normalize_fil_rouge_data(fil_rouge_data)

    exemple = get_insertion(fil_rouge_data, chapitre, section)

    request_contents = (
        f"{prompt}\n\n"
        f"SECTION : {section_data.get('contenu', '')}\n\n"
        f"FIL ROUGE : {exemple}\n\n"
        f"NUMERO CHAPITRE : {chapitre}\n\n"
        f"NUMERO SECTION : {section}"
    )

    parsed_response = _generate_json_with_retry(
        contents=(
            f"{request_contents}\n\n"
            "IMPORTANT: retourne un JSON strictement valide. "
            "Echappe tous les backslashes (\\\\) et n'utilise aucun caractere d'echappement invalide."
        ),
        context_label=f"merge_filrouge_ch{chapitre}_s{section}",
    )
    section_data["contenu"] = (
        parsed_response.get("section_mise_a_jour")
        or parsed_response.get("contenu")
        or section_data.get("contenu", "")
    )
    return section_data


def _normalize_resume_from(resume_from):
    if not isinstance(resume_from, dict):
        return None
    try:
        ch_num = int(resume_from.get("chapitre"))
        sec_num = int(resume_from.get("section"))
    except (TypeError, ValueError):
        return None
    return {"chapitre": ch_num, "section": sec_num}


def _find_start_indices(chapitres, start_from):
    if not start_from:
        return 0, 0

    target = _normalize_resume_from(start_from)
    if not target:
        print("Point de reprise merge fil rouge invalide, reprise depuis le debut.")
        return 0, 0

    for chap_idx, chapitre in enumerate(chapitres):
        chapitre_num = int(chapitre.get("numero", 0))
        if chapitre_num != target["chapitre"]:
            continue

        for sec_idx, section in enumerate(chapitre.get("sections", [])):
            section_num = int(section.get("numero", 0))
            if section_num == target["section"]:
                return chap_idx, sec_idx

    print("Point de reprise merge fil rouge introuvable, reprise depuis le debut.")
    return 0, 0


def merge_filrouge_wrapper(start_from=None):
    chapitres = load_structure()
    chap_idx, sec_start_idx = _find_start_indices(chapitres, start_from)
    start_chap_idx = chap_idx

    if start_from and (chap_idx != 0 or sec_start_idx != 0):
        start_ch = int(chapitres[chap_idx]["numero"])
        start_sec = int(chapitres[chap_idx]["sections"][sec_start_idx]["numero"])
        print(f"Reprise merge fil rouge activee depuis chapitre {start_ch} section {start_sec}.")

    while chap_idx < len(chapitres):
        chapitre = chapitres[chap_idx]
        chapitre_num = int(chapitre["numero"])

        start_idx_for_chapter = sec_start_idx if chap_idx == start_chap_idx else 0
        for section in chapitre.get("sections", [])[start_idx_for_chapter:]:
            section_num = int(section["numero"])
            result = incorporer(chapitre_num, section_num)
            print(f"Résultat pour Chapitre {chapitre_num} Section {section_num}\n{'-' * 80}")

            filepath = SECTION_DIR / f"section_ch{chapitre_num}_s{section_num}.json"
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        chap_idx += 1
        sec_start_idx = 0


if __name__ == '__main__':
    merge_filrouge_wrapper()