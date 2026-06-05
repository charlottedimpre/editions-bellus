import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from ...models import FicheSection, FilRouge, FilRougeInsertion, SectionTexteEnrichi, SectionTexte
from ...settings import BASE_DIR
from ..fiche_cadrage import recup_fiche_cadrage
from ..parser import parse_filrouge, parse_resume, read_text_file
from ..plan_detaille import recup_plan_detail
from ..structure_chapitre import recup_chapitres_sections
from .verification_filrouge import verify_all_sections_have_filrouge_entry

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT_DIR = Path(BASE_DIR).parents[0]
INPUT_DIR = Path(BASE_DIR) / "Stage/input/fil_rouge/"

load_dotenv(ROOT_DIR / "param.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier param.env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_FILROUGE_VALIDATION_ATTEMPTS = int(os.getenv("MAX_FILROUGE_VALIDATION_ATTEMPTS", "10"))
MAX_MERGE_SECTION_ATTEMPTS = 3
CLIENT = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _generate_text_with_retry(contents: str, context_label: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = CLIENT.models.generate_content(model=GEMINI_MODEL, contents=contents)
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
                f"Gemini indisponible (503) [{context_label}] tentative {attempt}/{MAX_RETRIES}, "
                f"nouvelle tentative dans {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Echec de generation Gemini ({context_label}).")


def _generate_json_with_retry(contents: str, context_label: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        response_text = _generate_text_with_retry(contents=contents, context_label=context_label)
        try:
            raw = response_text.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("La reponse du modele doit etre un objet JSON.")
            return parsed
        except json.JSONDecodeError as err:
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"JSON invalide apres {MAX_RETRIES} tentatives ({context_label}): {err}"
                ) from err
            print(f"JSON invalide [{context_label}] tentative {attempt}/{MAX_RETRIES}, nouvelle tentative...")
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Echec de parsing JSON ({context_label}).")


# ---------------------------------------------------------------------------
# Helpers structure + résumés
# ---------------------------------------------------------------------------

def load_structure(livre_id: int) -> list[dict]:
    data = json.loads(recup_chapitres_sections(livre_id))
    if not isinstance(data, list):
        raise ValueError("La structure des chapitres doit etre une liste.")
    return data


def build_resume_mashup(chapitres: list[dict], livre_id: int) -> list[dict]:
    """Construit le mashup des résumés de cohérence depuis FicheSection en BDD."""
    mashup = []

    for chapitre in chapitres:
        if not isinstance(chapitre, dict):
            continue
        ch_num = int(chapitre.get("numero", 0))
        sections = chapitre.get("sections", [])
        if not isinstance(sections, list):
            raise ValueError(f"chapitre.sections invalide pour chapitre {ch_num}")

        for section in sections:
            if not isinstance(section, dict):
                continue
            sec_num = int(section.get("numero", 0))

            try:
                fiche = FicheSection.objects.get(
                    chapitre_numero=ch_num,
                    section_numero=sec_num,
                    livre_id=livre_id,
                )
                coherence = {
                    "chapitre": fiche.chapitre_numero,
                    "section": fiche.section_numero,
                    "these_centrale": fiche.these_centrale,
                    "arguments_cles": fiche.arguments_cles,
                    "concepts_introduits": fiche.concepts_introduits,
                    "a_ne_pas_repeter": fiche.a_ne_pas_repeter,
                    "liens_chapitres": fiche.liens_chapitres,
                    "ton_angle": fiche.ton_angle,
                }
                mashup.append({"chapitre": ch_num, "section": sec_num, "resume": coherence})
            except FicheSection.DoesNotExist:
                mashup.append({"chapitre": ch_num, "section": sec_num, "resume": None, "missing": True})

    mashup.sort(key=lambda x: (x["chapitre"], x["section"]))
    return mashup


# ---------------------------------------------------------------------------
# gen_filrouge
# ---------------------------------------------------------------------------

def gen_filrouge(livre_id: int) -> dict:
    chapitres = load_structure(livre_id)
    fiche_raw = recup_fiche_cadrage(livre_id)
    plan_raw = recup_plan_detail(livre_id)
    resume_mashup = build_resume_mashup(chapitres, livre_id)

    prompt_path = INPUT_DIR / "fr_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt fil rouge", require_non_empty=False)

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
    if not isinstance(parsed, dict):
        raise ValueError("Le fil rouge parse doit etre un objet JSON.")

    ajout_filrouge_insertions_bdd(parsed, livre_id)
    return parsed


def gen_filrouge_with_validation(
    livre_id: int,
    max_attempts: int = MAX_FILROUGE_VALIDATION_ATTEMPTS,
) -> dict:
    if max_attempts < 1:
        raise ValueError("max_attempts doit etre >= 1")

    last_report = None
    for attempt in range(1, max_attempts + 1):
        parsed = gen_filrouge(livre_id)
        report = verify_all_sections_have_filrouge_entry(livre_id)
        last_report = report

        if report.get("ok"):
            if attempt > 1:
                print(f"Fil rouge complet apres {attempt} tentatives.")
            return parsed

        missing_count = len(report.get("missing", []))
        print(
            f"Fil rouge incomplet apres tentative {attempt}/{max_attempts}: "
            f"{missing_count} sections manquantes."
        )

    missing_preview = (last_report or {}).get("missing", [])[:5]
    raise RuntimeError(
        f"Generation du fil rouge incomplete apres {max_attempts} tentatives. "
        f"Exemples de sections manquantes: {missing_preview}"
    )


# ---------------------------------------------------------------------------
# merge_filrouge
# ---------------------------------------------------------------------------

def get_insertion(livre_id: int, chapitre: int, section: int) -> str:
    try:
        ins = FilRougeInsertion.objects.get(
            chapitre_numero=chapitre,
            section_numero=section,
            livre_id=livre_id,
        )
        return ins.contenu or ""
    except FilRougeInsertion.DoesNotExist:
        return ""


def incorporer(chapitre: int, section: int, livre_id: int) -> str:
    """Fusionne la section existante avec son insertion fil rouge."""
    prompt_path = INPUT_DIR / "mf_prompt.txt"
    prompt = read_text_file(prompt_path, "prompt merge fil rouge", require_non_empty=False)

    # Section originale depuis BDD
    section_obj = SectionTexte.objects.get(
        chapitre=chapitre,
        section=section,
        livre_id=livre_id,
    )
    section_contenu = section_obj.contenu or ""

    # Insertion fil rouge depuis BDD
    insertion = get_insertion(livre_id, chapitre, section)

    parsed_response = _generate_json_with_retry(
        contents=(
            f"{prompt}\n\n"
            f"SECTION : {section_contenu}\n\n"
            f"FIL ROUGE : {insertion}\n\n"
            f"NUMERO CHAPITRE : {chapitre}\n\n"
            f"NUMERO SECTION : {section}\n\n"
            "IMPORTANT: retourne un JSON strictement valide. "
            "Echappe tous les backslashes (\\\\) et n'utilise aucun caractere d'echappement invalide."
        ),
        context_label=f"merge_filrouge_ch{chapitre}_s{section}",
    )

    contenu_enrichi = (
        parsed_response.get("section_mise_a_jour")
        or parsed_response.get("contenu")
        or section_contenu
    )
    return contenu_enrichi


def _verify_single_section_size(chapitre: int, section: int, livre_id: int) -> dict:
    """Vérifie que len(section_enrichie) > len(section_originale)."""
    try:
        original = SectionTexte.objects.get(chapitre=chapitre, section=section, livre_id=livre_id)
        original_len = len(original.contenu or "")
    except SectionTexte.DoesNotExist:
        return {"ok": False, "error": "missing_section_originale"}

    try:
        enrichi = SectionTexteEnrichi.objects.get(chapitre=chapitre, section=section, livre_id=livre_id)
        enrichi_len = len(enrichi.contenu or "")
    except SectionTexteEnrichi.DoesNotExist:
        return {"ok": False, "error": "missing_section_enrichie"}

    ok = enrichi_len > original_len
    return {
        "ok": ok,
        "section_length": original_len,
        "section_fr_length": enrichi_len,
        "error": None if ok else "invalid_order",
    }


def merge_filrouge_wrapper(livre_id: int, start_from=None):
    chapitres = load_structure(livre_id)

    # Détermination du point de départ
    chap_start, sec_start = 0, 0
    if start_from and isinstance(start_from, dict):
        try:
            target_ch = int(start_from.get("chapitre", 0))
            target_sec = int(start_from.get("section", 0))
            for ci, chap in enumerate(chapitres):
                if int(chap.get("numero", 0)) != target_ch:
                    continue
                for si, sec in enumerate(chap.get("sections", [])):
                    if int(sec.get("numero", 0)) == target_sec:
                        chap_start, sec_start = ci, si
                        break
        except (TypeError, ValueError):
            print("Point de reprise invalide, reprise depuis le debut.")

    start_chap_idx = chap_start

    for chap_idx in range(chap_start, len(chapitres)):
        chap = chapitres[chap_idx]
        if not isinstance(chap, dict):
            continue

        ch_num = int(chap.get("numero", 0))
        sections = chap.get("sections", [])
        start_idx = sec_start if chap_idx == start_chap_idx else 0

        for sec in sections[start_idx:]:
            if not isinstance(sec, dict):
                continue
            sec_num = int(sec.get("numero", 0))
            section_ok = False

            for attempt in range(1, MAX_MERGE_SECTION_ATTEMPTS + 1):
                contenu_enrichi = incorporer(ch_num, sec_num, livre_id)
                ajout_section_enrichie_bdd(ch_num, sec_num, contenu_enrichi, livre_id)

                size_check = _verify_single_section_size(ch_num, sec_num, livre_id)
                if size_check["ok"]:
                    section_ok = True
                    print(f"Merge OK — chapitre {ch_num} section {sec_num} (tentative {attempt}/{MAX_MERGE_SECTION_ATTEMPTS})")
                    break

                print(
                    f"[WARN] Merge invalide section_ch{ch_num}_s{sec_num} "
                    f"(tentative {attempt}/{MAX_MERGE_SECTION_ATTEMPTS}) | "
                    f"original={size_check.get('section_length')} | "
                    f"enrichi={size_check.get('section_fr_length')}"
                )

            if not section_ok:
                raise RuntimeError(
                    f"Echec merge_filrouge pour section_ch{ch_num}_s{sec_num}: "
                    f"section enrichie pas plus longue que l'originale "
                    f"apres {MAX_MERGE_SECTION_ATTEMPTS} tentatives."
                )


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_filrouge_insertions_bdd(parsed: dict, livre_id: int):
    """Sauvegarde toutes les insertions du fil rouge en BDD."""
    FilRougeInsertion.objects.filter(livre_id=livre_id).delete()

    for ins in parsed.get("insertions", []):
        if not isinstance(ins, dict):
            continue
        chapitre_num = ins.get("chapitre")
        section_num = ins.get("section")
        contenu = ins.get("contenu") or ins.get("passage") or ""

        if chapitre_num is None or section_num is None:
            continue

        FilRougeInsertion.objects.create(
            chapitre_numero=int(chapitre_num),
            section_numero=int(section_num),
            contenu=contenu,
            livre_id=livre_id,
        )

    print(f"FilRougeInsertions sauvegardees : {len(parsed.get('insertions', []))} insertions.")


def ajout_section_enrichie_bdd(chapitre: int, section: int, contenu: str, livre_id: int):
    SectionTexteEnrichi.objects.update_or_create(
        chapitre=chapitre,
        section=section,
        livre_id=livre_id,
        defaults={"contenu": contenu},
    )


def recup_filrouge_insertions(livre_id: int) -> str:
    insertions = FilRougeInsertion.objects.filter(livre_id=livre_id).order_by(
        "chapitre_numero", "section_numero"
    )
    return json.dumps(
        {
            "insertions": [
                {
                    "chapitre": ins.chapitre_numero,
                    "section": ins.section_numero,
                    "contenu": ins.contenu,
                }
                for ins in insertions
            ]
        },
        ensure_ascii=False,
        indent=2,
    )


def recup_section_enrichie(chapitre: int, section: int, livre_id: int) -> str:
    obj = SectionTexteEnrichi.objects.get(chapitre=chapitre, section=section, livre_id=livre_id)
    return json.dumps(
        {"chapitre": obj.chapitre, "section": obj.section, "contenu": obj.contenu},
        ensure_ascii=False,
        indent=2,
    )


def recup_sections_enrichies_all(livre_id: int) -> list[dict]:
    return list(
        SectionTexteEnrichi.objects.filter(livre_id=livre_id)
        .order_by("chapitre", "section")
        .values("chapitre", "section", "contenu")
    )


def reset_filrouge_insertions(livre_id: int):
    FilRougeInsertion.objects.filter(livre_id=livre_id).delete()


def reset_sections_enrichies(livre_id: int):
    SectionTexteEnrichi.objects.filter(livre_id=livre_id).delete()


def reset_all_filrouge(livre_id: int):
    reset_filrouge_insertions(livre_id)
    reset_sections_enrichies(livre_id)
