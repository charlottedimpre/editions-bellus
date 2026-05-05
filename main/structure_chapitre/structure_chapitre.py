import json
import os
from pathlib import Path

from llm_fallback import chat_with_major_error_fallback

from parser import parse_structure_chapitres, read_json_file as _read_json, read_text_file as _read_text

MODEL = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT") or "mistral-large-3:675b-cloud"
LLM_MAX_RETRIES = 4
LLM_BASE_DELAY_SECONDS = 2

# Configuration centralisee pour faire evoluer facilement la cible globale.
WORD_TARGET_CONFIG = {
    "total_mots_cibles_livre": 15000,
    "fourchette_mots_ratio": 0.40,
}

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
PLAN_DETAIL_PATH = BASE_DIR.parent / "plan_detaille" / "output" / "plan_detaille.json"
CONFIG_PATH = BASE_DIR.parent / "config.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_word_target_config(mode: str | None) -> dict:
    config = dict(WORD_TARGET_CONFIG)
    if str(mode) != "1":
        return config

    if not CONFIG_PATH.exists():
        raise ValueError("Mode 1 actif: config.json introuvable pour charger les cibles de mots.")

    cfg = _read_json(CONFIG_PATH, "config")
    livre_cfg = cfg.get("livre", {}) if isinstance(cfg, dict) else {}

    raw_total = livre_cfg.get("nbre_mots_cible")
    if raw_total is None:
        raise ValueError("Mode 1 actif: 'livre.nbre_mots_cible' est requis dans config.json.")

    config["total_mots_cibles_livre"] = int(raw_total)

    raw_fourchette = livre_cfg.get("fourchette_mots_ratio", cfg.get("fourchette_mots_ratio"))
    if raw_fourchette is not None:
        config["fourchette_mots_ratio"] = float(raw_fourchette)

    return config


def _get_total_mots_cibles_livre(word_target_config: dict) -> int:
    total = int(word_target_config.get("total_mots_cibles_livre", 0))
    if total <= 0:
        raise ValueError("La configuration total_mots_cibles_livre doit etre un entier positif.")
    return total


def _add_word_count_per_section(chapitres: list[dict], word_target_config: dict) -> list[dict]:
    total_mots_livre = _get_total_mots_cibles_livre(word_target_config)
    # On repartit directement le total livre sur les sections.
    total_mots_structure = max(1, total_mots_livre)

    all_sections: list[dict] = []
    for chapitre in chapitres:
        sections = chapitre.get("sections")
        if not isinstance(sections, list) or not sections:
            continue
        for section in sections:
            if isinstance(section, dict):
                all_sections.append(section)

    total_sections = len(all_sections)
    if total_sections <= 0:
        raise ValueError("Impossible de repartir les mots: aucune section valide detectee.")

    base = total_mots_structure // total_sections
    reste = total_mots_structure % total_sections
    fourchette_ratio = max(0.0, float(word_target_config.get("fourchette_mots_ratio", 0.40)))
    demi_fourchette = fourchette_ratio / 2

    for idx, section in enumerate(all_sections):
        mots_section = base + (1 if idx < reste else 0)
        mots_section = max(1, mots_section)

        min_mots = max(1, round(mots_section * (1 - demi_fourchette)))
        max_mots = max(min_mots, round(mots_section * (1 + demi_fourchette)))

        section["nombre_mots_section"] = mots_section
        section["mots_cible"] = f"{min_mots}-{max_mots}"

    for chapitre in chapitres:
        sections = chapitre.get("sections")
        if not isinstance(sections, list):
            chapitre["total_mots_chapitre"] = 0
            continue

        total_chapitre = 0
        for section in sections:
            if not isinstance(section, dict):
                continue
            total_chapitre += int(section.get("nombre_mots_section", 0) or 0)

        chapitre["total_mots_chapitre"] = total_chapitre

    return chapitres


def _get_candidate_models() -> list[str]:
    # Optional override/fallback list, comma-separated.
    # Example: ED_BELLUS_STRUCTURE_MODELS="mistral-large-3:675b-cloud,kimi-k2.5:cloud"
    raw = os.getenv("ED_BELLUS_STRUCTURE_MODELS", "").strip()
    if not raw:
        return [MODEL]

    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or [MODEL]


def _chat_with_retry(message_content: str, context_label: str) -> str:
    last_error: Exception | None = None
    models = _get_candidate_models()

    for model in models:
        try:
            return chat_with_major_error_fallback(
                ollama_model=model,
                message_content=message_content,
                context_label=context_label,
                ollama_max_retries=LLM_MAX_RETRIES,
                ollama_retry_delay_seconds=LLM_BASE_DELAY_SECONDS,
            )
        except Exception as exc:
            last_error = exc
            if len(models) > 1:
                print(f"[WARN] Echec avec le modele {model}. Tentative du modele suivant...")

    raise RuntimeError(
        f"Echec appel LLM pour {context_label} avec les modeles {', '.join(models)}: {last_error}"
    )


def structure_chapitre(mode: str = "0"):
    word_target_config = _resolve_word_target_config(mode)

    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    fiche_raw = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    _read_json(PLAN_DETAIL_PATH, "plan detaille")
    plan_raw = _read_text(PLAN_DETAIL_PATH, "plan detaille")

    prompt_path = INPUT_DIR / "sc_prompt.txt"
    prompt = _read_text(prompt_path, "prompt structure chapitre")

    raw_response = _chat_with_retry(
        message_content=f"{prompt}\n\nFICHE DE CADRAGE :{fiche_raw}\n\nPLAN DETAILLE :{plan_raw}",
        context_label="structure_chapitre",
    )

    parsed = parse_structure_chapitres(raw_response)
    if not isinstance(parsed, list):
        raise ValueError("La structure de chapitre parsee doit etre une liste.")

    if not parsed:
        raise ValueError("La structure de chapitre parsee est vide.")

    parsed = _add_word_count_per_section(parsed, word_target_config)

    filepath = OUTPUT_DIR / "structure_chapitre.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    return parsed


if __name__ == '__main__':
    structure_chapitre()