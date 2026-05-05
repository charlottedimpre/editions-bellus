import json
import os
from pathlib import Path

from llm_fallback import chat_with_major_error_fallback

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
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2
MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")


def _build_fiche_cadrage_for_prompt(payload: dict) -> dict:
    # Exclut les champs bruts/legacy pour eviter les contradictions dans le prompt.
    allowed_keys = [
        "sujet",
        "sommaire",
        "hors_perimetre",
        "contraintes_specifiques",
        "cible_principale",
        "niveau",
        "objectif_lecteur",
        "nbre_chapitres",
        "titre_saisi_utilisateur",
    ]
    return {key: payload.get(key) for key in allowed_keys if key in payload}


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


def _chat_with_retry(model: str, message_content: str, context_label: str) -> str:
    return chat_with_major_error_fallback(
        ollama_model=model,
        message_content=message_content,
        context_label=context_label,
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )


def plan_detail():
    input_path = INPUT_DIR / "pd_prompt.txt"
    prompt = _read_text(input_path, "prompt plan detaille")

    fiche_cadrage_payload = _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    expected_chapters = None
    if isinstance(fiche_cadrage_payload, dict):
        raw_expected = fiche_cadrage_payload.get("nbre_chapitres")
        if raw_expected is not None:
            expected_chapters = int(raw_expected)
        fiche_cadrage_for_prompt = _build_fiche_cadrage_for_prompt(fiche_cadrage_payload)
    else:
        fiche_cadrage_for_prompt = {"raw_fiche": fiche_cadrage_payload}

    fiche_cadrage = json.dumps(fiche_cadrage_for_prompt, ensure_ascii=False, indent=2)

    sources_web = json.dumps(sources(), ensure_ascii=False, indent=2)

    response_content = _chat_with_retry(
        model=MODEL_COURT,
        message_content=(
            f"{prompt}\n\n"
            f"FICHE DE CADRAGE (JSON) : {fiche_cadrage}\n\n"
            f"SOURCES WEB (JSON) : {sources_web}"
        ),
        context_label="plan_detaille",
    )

    parsed = parse_plan_detaille(response_content)
    if not isinstance(parsed, dict):
        raise ValueError("Le plan detaille parse doit etre un objet JSON.")

    chapitres = parsed.get("chapitres")
    if not isinstance(chapitres, list) or len(chapitres) == 0:
        raise ValueError("Le plan detaille parse doit contenir une liste de chapitres non vide.")
    if expected_chapters is not None and len(chapitres) != int(expected_chapters):
        print(
            f"[WARN] Nombre de chapitres invalide ({len(chapitres)} au lieu de {int(expected_chapters)}). "
            "Nouvelle tentative de generation forcee."
        )
        response_content = _chat_with_retry(
            model=MODEL_COURT,
            message_content=(
                f"{prompt}\n\n"
                f"FICHE DE CADRAGE (JSON) : {fiche_cadrage}\n\n"
                f"SOURCES WEB (JSON) : {sources_web}\n\n"
                f"CONTRAINTE ABSOLUE: genere EXACTEMENT {int(expected_chapters)} chapitres. "
                "Ne renvoie que le format demande."
            ),
            context_label="plan_detaille_count_fix",
        )
        parsed = parse_plan_detaille(response_content)
        chapitres = parsed.get("chapitres")
        if not isinstance(chapitres, list) or len(chapitres) != int(expected_chapters):
            raise ValueError(
                f"Nombre de chapitres invalide: attendu {int(expected_chapters)} depuis la fiche, obtenu {len(chapitres) if isinstance(chapitres, list) else 'invalide'} apres correction."
            )

    filepath = OUTPUT_DIR / "plan_detaille.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    clean_plan_detaille_titles_in_file(filepath)

    return parsed


if __name__ == '__main__':
    plan_detail()