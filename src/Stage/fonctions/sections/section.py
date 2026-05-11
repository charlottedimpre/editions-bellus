import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from ..parser import parse_section, parse_resume
from .section_cleaner import normalize_section_content, strip_leading_title

from ..check import (check_book_progress, get_resume_instructions)

from ..fiche_cadrage import recup_fiche_cadrage
from .. plan_detaille import recup_plan_detail
from .. structure_chapitre import recup_chapitres_sections

from ...settings import BASE_DIR
from ...models import *



ROOT_DIR = BASE_DIR.parents[0]


load_dotenv(ROOT_DIR / "param.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY introuvable dans le fichier param.env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
MAX_BOOK_WORDS = 15000
SECTION_WORD_RANGE = 300
MAX_SECTION_REGEN_ATTEMPTS = 3
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


def load_structure():
    """Charge structure_chapitre.json et retourne la liste des chapitres."""
    return recup_chapitres_sections()


def _find_section_title(chapitre: int, section: int) -> str | None:
    for chap in json.loads(load_structure()):
        if int(chap.get("numero", 0)) != chapitre:
            continue
        for sec in chap.get("sections", []):
            if int(sec.get("numero", 0)) == section:
                title = sec.get("titre_section")
                if isinstance(title, str) and title.strip():
                    return title.strip()
    return None


def _count_words(text: str) -> int:
    # Compte les mots en preservant les apostrophes/tirets dans les tokens.
    return len(re.findall(r"[\wÀ-ÖØ-öø-ÿ]+(?:['’-][\wÀ-ÖØ-öø-ÿ]+)*", text, flags=re.UNICODE))





def _compute_section_word_bounds(total_sections: int) -> tuple[int, int, int]:
    if total_sections <= 0:
        raise ValueError("Impossible de calculer les bornes: nombre total de sections invalide.")

    target_words = max(1, round(MAX_BOOK_WORDS / total_sections))
    half_range = max(1, SECTION_WORD_RANGE // 2)
    min_words = max(1, target_words - half_range)
    max_words = max(min_words, target_words + half_range)
    return min_words, max_words, target_words


def _count_total_sections(chapitres: list[dict]) -> int:
    return sum(len(chap.get("sections", [])) for chap in chapitres if isinstance(chap, dict))


def gen_section(chapitre, section):
    fiche = recup_fiche_cadrage()

    plan = recup_plan_detail()

    structure = recup_chapitres_sections()

    prompt = os.path.join(BASE_DIR, 'Stage/input/section/s_prompt.txt')
    file = open(prompt, 'r')
    prompt = file.read()

    structure_data = load_structure()
    structure_data = json.loads(structure_data)
    total_sections = _count_total_sections(structure_data)
    min_words, max_words, target_words = _compute_section_word_bounds(total_sections)
    print(
        f"Contraintes dynamiques section: cible {target_words} mots, plage {min_words}-{max_words} (total sections: {total_sections}, max livre: {MAX_BOOK_WORDS})."
    )

    coherence = ""
    if chapitre == 1 and section == 1:
        coherence = "il n'y a pas de section précédente, c'est la première section du premier chapitre, aucune vérification de cohérence nécessaire."
        print(f"{coherence}")
    elif section == 1:
        chapitres = structure_data
        nb_sec = None
        for chap in chapitres:
            if int(chap["numero"]) == chapitre - 1:
                nb_sec = len(chap["sections"])
                break

        if nb_sec is not None:
            coherence = recup_fiche_cadrage()
            print(f"Vérification de cohérence avec la section précédente : coherence_ch{chapitre - 1}_s{nb_sec}.json...")
        else:
            coherence = "Section précédente introuvable dans la structure."
            print(coherence)
    else:
        coherence = recup_fiche_cadrage()
        print(f"Vérification de cohérence avec la section précédente : coherence_ch{chapitre}_s{section - 1}.json...")

    coherence_text = coherence if coherence else ""

    for regen_attempt in range(1, MAX_SECTION_REGEN_ATTEMPTS + 1):
        response_text = _generate_text_with_retry(
            contents=f"{prompt}\n\nFICHE DE CADRAGE :{fiche}\n\nPLAN DÉTAILLÉ :{plan}\n\nFICHE DE STRUCTURE DU CHAPITRE : {structure}\n\nCHAPITRE À RÉDIGER : Chapitre {chapitre}\n\nSECTION À RÉDIGER : Section {section}\n\nCONTRAINTE DE LONGUEUR : vise environ {target_words} mots, accepte uniquement une section entre {min_words} et {max_words} mots.\n\nVérification de cohérence avec la section précédente : {coherence_text}",
            context_label=f"section_ch{chapitre}_s{section}",
        )

        parsed = parse_section(response_text, chapitre, section)

        # Nettoyage du contenu avant insertion dans le JSON de base.
        section_title = _find_section_title(chapitre, section)
        if section_title and isinstance(parsed.get("contenu"), str):
            cleaned_content, removed, matched_separator = strip_leading_title(
                parsed["contenu"], section_title
            )
            if removed:
                parsed["contenu"] = cleaned_content
                print(
                    f"Prefixe titre retire pour section_ch{chapitre}_s{section} ({matched_separator!r})."
                )

        ajout_section_texte(parsed)

        contenu = parsed.get("contenu", "")
        word_count = len(contenu.split())
        print(
            f"Section {section} du chapitre {chapitre} sauvegardée ({word_count} mots)."
        )

        if min_words <= word_count <= max_words:
            coherence_check(chapitre, section)
            print(
                f"Longueur valide ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). Vérification de cohérence effectuée."
            )
            return

        if regen_attempt == MAX_SECTION_REGEN_ATTEMPTS:
            raise RuntimeError(
                f"Section section_ch{chapitre}_s{section} hors plage ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}) apres {MAX_SECTION_REGEN_ATTEMPTS} tentatives."
            )

        length_issue = "trop courte" if word_count < min_words else "trop longue"
        print(
            f"Section section_ch{chapitre}_s{section} {length_issue} ({word_count} mots, attendu {min_words}-{max_words}, cible {target_words}). Regeneration ({regen_attempt}/{MAX_SECTION_REGEN_ATTEMPTS})..."
        )


def coherence_check(chapitre, section):
    fiche = recup_section_texte(chapitre, section)

    prompt = os.path.join(BASE_DIR, 'Stage/input/section/c_prompt.txt')
    file = open(prompt, 'r')
    prompt = file.read()


    response_text = _generate_text_with_retry(
        contents=f"{prompt}\n\nSection à étudier :{fiche}",
        context_label=f"coherence_ch{chapitre}_s{section}",
    )
    parsed = parse_resume(response_text, chapitre, section)

    #Ajout cohérence bdd
    ajout_fiche_section(parsed)

    return parsed








def _normalize_resume_from(resume_from):
    if not isinstance(resume_from, dict):
        return None
    try:
        ch_num = int(resume_from.get("chapitre"))
        sec_num = int(resume_from.get("section"))
    except (TypeError, ValueError):
        return None
    return {"chapitre": ch_num, "section": sec_num}


def _run_resume_auto(auto_confirm=False):
    instructions = get_resume_instructions()

    if not instructions.get("possible"):
        print("Aucune reprise necessaire: le pipeline semble termine.")
        return instructions

    next_step = instructions.get("next_step")
    next_function = instructions.get("next_function")
    resume_from = instructions.get("resume_from")

    print(f"Reprise automatique detectee -> etape: {next_step}")
    if resume_from:
        print(f"Point de reprise conseille: {resume_from}")

    if not next_function:
        print("Impossible de reprendre automatiquement: fonction cible introuvable.")
        return instructions

    print(f"Lancement de suivi('{next_function}')...")
    return instructions

def _section(ch_num, sec_num):
    print(f"Génération de la section {sec_num} du chapitre {ch_num}...")


def _find_start_indices(chapitres, start_from):
    if not start_from:
        return 0, 0

    target = _normalize_resume_from(start_from)
    if not target:
        print("Point de reprise invalide, reprise depuis le debut des sections.")
        return 0, 0

    for chap_idx, chap in enumerate(chapitres):
        ch_num = int(chap["numero"])
        if ch_num != target["chapitre"]:
            continue

        for sec_idx, sec in enumerate(chap.get("sections", [])):
            sec_num = int(sec["numero"])
            if sec_num == target["section"]:
                return chap_idx, sec_idx

    print("Point de reprise introuvable dans la structure, reprise depuis le debut des sections.")
    return 0, 0


def _infer_start_from_generated_sections():
    """Deduit le point de reprise a partir des fichiers deja presents dans output."""
    progress = check_book_progress()
    reprise = progress.get("reprise", {})

    if reprise.get("next_function") == "gen_all_sections" and reprise.get("resume_from"):
        return reprise.get("resume_from")

    missing_sections = progress.get("manquants", {}).get("sections_brutes", [])
    if missing_sections:
        return missing_sections[0]

    # Si toutes les sections existent mais qu'un resume de coherence manque,
    # on reprend a la section concernee pour regenerer resume + suite coherente.
    missing_resumes = progress.get("manquants", {}).get("resumes_coherence", [])
    if missing_resumes:
        return missing_resumes[0]

    return None

def suivisection(start_from=None, auto_confirm=False):
    status, _ = ProcessStatus.objects.get_or_create(id=1)


    chapitres = load_structure()
    chapitres = json.loads(chapitres)
    nb_chapitres = len(chapitres)
    nb_total_sections = sum(len(ch["sections"]) for ch in chapitres)

    print(f"Structure chargée : {nb_chapitres} chapitres, {nb_total_sections} sections au total\n")

    if start_from is None:
        start_from = _infer_start_from_generated_sections()
        if start_from:
            print(f"Reprise detectee depuis les sections generees: {start_from}")

    chap_idx, sec_start_idx = _find_start_indices(chapitres, start_from)
    start_chap_idx = chap_idx

    if start_from and (chap_idx != 0 or sec_start_idx != 0):
        print(f"Reprise fine activee depuis chapitre {chapitres[chap_idx]['numero']} section {chapitres[chap_idx]['sections'][sec_start_idx]['numero']}.")

    while chap_idx < nb_chapitres:
        chap = chapitres[chap_idx]
        ch_num = int(chap["numero"])
        nb_sec = len(chap["sections"])
        print(f"Chapitre {ch_num} — {chap['titre']} ({nb_sec} sections)")

        start_idx_for_chapter = sec_start_idx if chap_idx == start_chap_idx else 0
        for sec in chap["sections"][start_idx_for_chapter:]:
            sec_num = int(sec["numero"])
            max_attempts = 10
            for attempt in range(1, max_attempts + 1):
                    status.message = "Redémarrage Celery..."
                    status.save()
                    _section(ch_num, sec_num)
                    gen_section(ch_num, sec_num)
                    break
                #except Exception as e:
                  #  print(f"Erreur section {sec_num} (chapitre {ch_num}) tentative {attempt}/{max_attempts}: {e}")
        chap_idx += 1
        #if auto_confirm:
            #avis_createur = '1'
        #else:
            #avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")
            #while avis_createur not in ['1', '2']:
                #print("Le nombre entré doit être 1 ou 2.")
                #avis_createur = input("Le résultat de la fonction est-il satisfaisant ? Oui (1) / Non (2) : ")

        #if avis_createur == '1':
            #print("Étape validée")
            #chap_idx += 1
            #sec_start_idx = 0
        #else:
            #print("Étape à retravailler")
            #continue

def ajout_fiche_section(data):
        chapitre_num = int(data.get("chapitre"))
        section_num = int(data.get("section"))

        section = SectionDetaillee.objects.get(
            chapitre__numero=chapitre_num,
            numero=section_num
        )

        FicheSection.objects.create(
            section=section,
            chapitre_numero=chapitre_num,
            section_numero=section_num,
            these_centrale=data.get("these_centrale"),
            arguments_cles=data.get("arguments_cles"),
            concepts_introduits=data.get("concepts_introduits"),
            a_ne_pas_repeter=data.get("a_ne_pas_repeter"),
            liens_chapitres=data.get("liens_chapitres"),
            ton_angle=data.get("ton_angle"),
            raw=data.get("_raw"),
        )

        print("FicheSection ajoutée avec succès")



def ajout_section_texte(data):
    SectionTexte.objects.update_or_create(
        chapitre=data.get("chapitre"),
        section=data.get("section"),
        defaults={
            "contenu": data.get("contenu"),
        }
    )

def ajout_resume_section(data):
        chapitre_num = int(data.get("chapitre"))
        section_num = int(data.get("section"))

        section = SectionDetaillee.objects.get(
            chapitre__numero=chapitre_num,
            numero=section_num
        )

        ResumeSection.objects.update_or_create(
            section=section,
            defaults={
                "chapitre_numero": chapitre_num,
                "section_numero": section_num,
                "resume": data.get("resume"),
            }
        )

        print("ResumeSection ajouté/mis à jour avec succès")

def recup_fiche_section(chapitre_num, section_num):
        fiche = FicheSection.objects.get(
            chapitre_numero=chapitre_num,
            section_numero=section_num
        )

        return json.dumps({
            "chapitre": fiche.chapitre_numero,
            "section": fiche.section_numero,
            "these_centrale": fiche.these_centrale,
            "arguments_cles": fiche.arguments_cles,
            "concepts_introduits": fiche.concepts_introduits,
            "liens_chapitres": fiche.liens_chapitres,
            "a_ne_pas_repeter": fiche.a_ne_pas_repeter,
            "ton_angle": fiche.ton_angle,
            "_raw": fiche.raw
        }, ensure_ascii=False, indent=2)

def recup_section_texte(chapitre_num, section_num):
        section = SectionTexte.objects.get(
            chapitre=chapitre_num,
            section=section_num
        )

        return json.dumps({
            "chapitre": section.chapitre,
            "section": section.section,
            "contenu": section.contenu
        }, ensure_ascii=False, indent=2)

def recup_section_texte_all():
    sections = SectionTexte.objects.all().order_by("chapitre", "section")

    chapitres_struct = ChapitreDetails.objects.prefetch_related("sections").all()

    titres = {}

    for chap in chapitres_struct:
        for sec in chap.sections.all():
            titres[(int(chap.numero), int(sec.numero))] = {
                "titre_chapitre": chap.titre,
                "titre_section": sec.titre_section
            }

    result = []

    for s in sections:
        key = (int(s.chapitre), int(s.section))
        info = titres.get(key, {})

        result.append({
            "chapitre": s.chapitre,
            "section": s.section,
            "titre_chapitre": info.get("titre_chapitre"),
            "titre_section": info.get("titre_section"),
            "contenu": s.contenu,
        })

    return result

def reset_section_texte():
    SectionTexte.objects.all().delete()

def reset_resume_section():
    ResumeSection.objects.all().delete()

def reset_contenu_section():
    ContenuSection().objects.all().delete()

def reset_fiche_section():
    FicheSection.objects.all().delete()

def reset_all_test():
    reset_section_texte()
    reset_resume_section()
    reset_fiche_section()
