import json
from pathlib import Path

from ollama import ChatResponse, chat

from parser import (
    clean_plan_detaille_titles_in_file,
    parse_plan_detaille,
    read_json_file as _read_json,
    read_text_file as _read_text,
)

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
WS_FINAL_PATH = BASE_DIR.parent / "web_search" / "output" / "ws_final.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_ws_final(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"sources_web": payload}
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {"sources_web": []}
        try:
            parsed = json.loads(text)
            return _normalize_ws_final(parsed)
        except json.JSONDecodeError:
            return {"sources_web_raw": text}
    return {"sources_web_raw": str(payload)}


def sources() -> dict:
    payload = _read_json(WS_FINAL_PATH, "sources web")
    return _normalize_ws_final(payload)


def plan_detail():
    input_path = INPUT_DIR / "pd_prompt.txt"
    prompt = _read_text(input_path, "prompt plan detaille")

    fiche_cadrage_payload = _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    expected_chapters = fiche_cadrage_payload.get("nbre_chapitres") if isinstance(fiche_cadrage_payload, dict) else None
    fiche_cadrage = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    sources_web = json.dumps(sources(), ensure_ascii=False, indent=2)

    response: ChatResponse = chat(model="mistral-large-3:675b-cloud", messages=[
        {
            "role": "user",
            "content": (
                f"{prompt}\n\n"
                f"FICHE DE CADRAGE : {fiche_cadrage}\n\n"
                f"SOURCES WEB (JSON) : {sources_web}"
            ),
        },
    ])

    if response.message is None or not response.message.content:
        raise ValueError("Reponse vide du modele pour le plan detaille.")

    parsed = parse_plan_detaille(response.message.content)
    if not isinstance(parsed, dict):
        raise ValueError("Le plan detaille parse doit etre un objet JSON.")

    chapitres = parsed.get("chapitres")
    if not isinstance(chapitres, list) or len(chapitres) == 0:
        raise ValueError("Le plan detaille parse doit contenir une liste de chapitres non vide.")
    if expected_chapters is not None and len(chapitres) != int(expected_chapters):
        raise ValueError(
            f"Nombre de chapitres invalide: attendu {int(expected_chapters)} depuis la fiche, obtenu {len(chapitres)}."
        )

    filepath = OUTPUT_DIR / "plan_detaille.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    clean_plan_detaille_titles_in_file(filepath)

    return parsed


if __name__ == '__main__':
    plan_detail()