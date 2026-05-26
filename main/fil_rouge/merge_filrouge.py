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

from parser import (
    normalize_resume_from,
    parse_filrouge,
    read_json_file,
    read_text_file,
    to_int_or_raise as _to_int,
    write_json_file as _write_json,
)

try:
    from fil_rouge.verification_merge_filrouge import verify_single_section_size
except ModuleNotFoundError:
    from verification_merge_filrouge import verify_single_section_size

load_dotenv(ROOT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier .env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL")
MAX_RETRIES = 10
RETRY_DELAY_SECONDS = 5
MAX_MERGE_SECTION_ATTEMPTS = 10
CLIENT = genai.Client(api_key=GEMINI_API_KEY)

def _read_text(path: Path, label: str) -> str:
    return read_text_file(path, label, require_non_empty=False)


def _read_json(path: Path, label: str):
    return read_json_file(path, label, require_non_empty=False)


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    structure = _read_json(STRUCTURE_PATH, "structure des chapitres")
    if not isinstance(structure, list):
        raise ValueError("La structure des chapitres doit etre une liste.")
    return structure


def get_insertion(fil_rouge_data: dict, chapitre: int, section: int) -> str:
    for ins in fil_rouge_data.get("insertions", []):
        if not isinstance(ins, dict):
            continue
        try:
            ins_chapitre = _to_int(ins.get("chapitre", -1), "insertion.chapitre")
            ins_section = _to_int(ins.get("section", -1), "insertion.section")
        except ValueError:
            continue
        if ins_chapitre == int(chapitre) and ins_section == int(section):
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
    prompt = _read_text(prompt_path, "prompt merge fil rouge")

    section_path = SECTION_OUTPUT_DIR / f"section_ch{chapitre}_s{section}.json"
    section_data = _read_json(section_path, f"section ch{chapitre} s{section}")
    if not isinstance(section_data, dict):
        raise ValueError(f"Format invalide pour la section ch{chapitre} s{section}: objet JSON attendu.")

    fil_rouge_data = _read_json(FIL_ROUGE_PATH, "fil rouge")
    fil_rouge_data = _normalize_fil_rouge_data(fil_rouge_data)
    if not isinstance(fil_rouge_data, dict):
        raise ValueError("Le fil rouge normalise doit etre un objet JSON.")

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
    return normalize_resume_from(resume_from)


def _find_start_indices(chapitres, start_from):
    if not start_from:
        return 0, 0

    target = _normalize_resume_from(start_from)
    if not target:
        print("Point de reprise merge fil rouge invalide, reprise depuis le debut.")
        return 0, 0

    for chap_idx, chapitre in enumerate(chapitres):
        if not isinstance(chapitre, dict):
            continue
        try:
            chapitre_num = _to_int(chapitre.get("numero", 0), "chapitre.numero")
        except ValueError:
            continue
        if chapitre_num != target["chapitre"]:
            continue

        for sec_idx, section in enumerate(chapitre.get("sections", [])):
            if not isinstance(section, dict):
                continue
            try:
                section_num = _to_int(section.get("numero", 0), "section.numero")
            except ValueError:
                continue
            if section_num == target["section"]:
                return chap_idx, sec_idx

    print("Point de reprise merge fil rouge introuvable, reprise depuis le debut.")
    return 0, 0


def merge_filrouge_wrapper(start_from=None):
    chapitres = load_structure()
    SECTION_DIR.mkdir(parents=True, exist_ok=True)
    chap_idx, sec_start_idx = _find_start_indices(chapitres, start_from)
    start_chap_idx = chap_idx

    if start_from and (chap_idx != 0 or sec_start_idx != 0):
        start_ch = _to_int(chapitres[chap_idx]["numero"], "chapitre.numero")
        start_sec = _to_int(chapitres[chap_idx]["sections"][sec_start_idx]["numero"], "section.numero")
        print(f"Reprise merge fil rouge activee depuis chapitre {start_ch} section {start_sec}.")

    while chap_idx < len(chapitres):
        chapitre = chapitres[chap_idx]
        if not isinstance(chapitre, dict):
            chap_idx += 1
            sec_start_idx = 0
            continue

        chapitre_num = _to_int(chapitre.get("numero"), "chapitre.numero")

        start_idx_for_chapter = sec_start_idx if chap_idx == start_chap_idx else 0
        for section in chapitre.get("sections", [])[start_idx_for_chapter:]:
            if not isinstance(section, dict):
                continue

            section_num = _to_int(section.get("numero"), f"section.numero (chapitre {chapitre_num})")
            filepath = SECTION_DIR / f"section_ch{chapitre_num}_s{section_num}.json"
            section_ok = False
            last_result = None
            last_size_check = None

            for attempt in range(1, MAX_MERGE_SECTION_ATTEMPTS + 1):
                result = incorporer(chapitre_num, section_num)
                last_result = result
                _write_json(filepath, result, f"section mergee ch{chapitre_num} s{section_num}")

                size_check = verify_single_section_size(
                    chapitre=chapitre_num,
                    section=section_num,
                    section_dir=SECTION_OUTPUT_DIR,
                    section_fr_dir=SECTION_DIR,
                )
                last_size_check = size_check
                if size_check["ok"]:
                    section_ok = True
                    print(
                        f"Résultat pour Chapitre {chapitre_num} Section {section_num} "
                        f"(tentative {attempt}/{MAX_MERGE_SECTION_ATTEMPTS})\n{'-' * 80}"
                    )
                    break

                print(
                    f"[WARN] Merge invalide pour section_ch{chapitre_num}_s{section_num} "
                    f"(tentative {attempt}/{MAX_MERGE_SECTION_ATTEMPTS}) | "
                    f"section={size_check.get('section_length')} | "
                    f"section_fr={size_check.get('section_fr_length')}"
                )

            if not section_ok:
                print(
                    f"[WARN] Merge fil rouge non conforme pour section_ch{chapitre_num}_s{section_num} "
                    f"apres {MAX_MERGE_SECTION_ATTEMPTS} tentatives. "
                    f"Derniere version conservee | "
                    f"section={last_size_check.get('section_length') if last_size_check else 'NA'} | "
                    f"section_fr={last_size_check.get('section_fr_length') if last_size_check else 'NA'}"
                )

        chap_idx += 1
        sec_start_idx = 0


if __name__ == '__main__':
    merge_filrouge_wrapper()