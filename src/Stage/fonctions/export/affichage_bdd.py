"""
affichage_bdd.py — fonctions de chargement des données depuis la BDD.
Utilisé par affichage_pdf.py, affichage_doc.py, affichage_md.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...models import ChapitreDetails, FicheCadrage, SectionDetaillee, SectionTexteEnrichi, SectionTexte
from ..conclusion import recup_conclusion
from ..fiche_cadrage import recup_fiche_cadrage
from ..introduction import recup_intro

BASE_DIR = Path(__file__).resolve().parent
PDF_TITLE = "Introduction"
AUTHOR_PLACEHOLDER = "Lise Genest"
PUBLISHER_NAME = "Editions Bellus"
BOOK_FORMAT_6X9_MM = (152.4, 228.6)
SIGNATURE_TEXT = "— Éditions Bellus"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def load_intro(livre_id: int) -> str:
    raw = recup_intro(livre_id)
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return _extract_text(payload.get("intro"))
    return _extract_text(payload)


def load_conclusion(livre_id: int) -> str:
    raw = recup_conclusion(livre_id)
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return _extract_text(payload.get("conclusion") or payload.get("_raw"))
    return _extract_text(payload)


def load_book_title(livre_id: int) -> str:
    raw = recup_fiche_cadrage(livre_id)
    payload = json.loads(raw)

    # Cherche dans la liste fiche_cadrage si présent
    if isinstance(payload, dict):
        fiche_list = payload.get("fiche_cadrage", [])
        if fiche_list and isinstance(fiche_list, list):
            sujet = fiche_list[0].get("sujet")
            if sujet:
                return _extract_text(sujet)
        # Fallback direct
        sujet = payload.get("sujet") or payload.get("titre_saisi_utilisateur")
        if sujet:
            return _extract_text(sujet)

    # Fallback BDD directe
    fiche = FicheCadrage.objects.filter(livre_id=livre_id).first()
    if fiche and fiche.sujet:
        return _extract_text(fiche.sujet)

    return PDF_TITLE


def load_preface(livre_id: int) -> str:
    """À implémenter quand le modèle Preface sera disponible."""
    return ""


def load_postface(livre_id: int) -> str:
    """À implémenter quand le modèle Postface sera disponible."""
    return ""


def load_chapters(livre_id: int) -> list[dict[str, Any]]:
    """
    Charge les chapitres avec leurs sections enrichies (fil rouge)
    depuis SectionTexteEnrichi.
    """
    chapitres_qs = ChapitreDetails.objects.filter(
        livre_id=livre_id
    ).prefetch_related("sections").order_by("numero")

    # Index des contenus enrichis
    enrichis = SectionTexteEnrichi.objects.filter(livre_id=livre_id)
    enrichi_map: dict[tuple[int, int], str] = {
        (e.chapitre, e.section): e.contenu or ""
        for e in enrichis
    }

    chapters_data: list[dict[str, Any]] = []

    for chap in chapitres_qs:
        sections_data: list[dict[str, Any]] = []

        for sec in chap.sections.all().order_by("numero"):
            contenu = enrichi_map.get((int(chap.numero), int(sec.numero)), "")
            sections_data.append({
                "titre": _extract_text(sec.titre_section),
                "contenu": _extract_text(contenu),
            })

        chapters_data.append({
            "chapitre": str(chap.numero),
            "titre": _extract_text(chap.titre),
            "sections": sections_data,
        })

    return chapters_data


def build_toc_entries(
    chapters: list[dict[str, Any]],
    has_preface: bool,
    has_conclusion: bool,
    has_postface: bool,
) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    if has_preface:
        entries.append(("preface", "Préface"))
    entries.append(("intro", "Introduction"))
    for index, chapter_data in enumerate(chapters, start=1):
        chapter_number = _extract_text(chapter_data.get("chapitre") or index)
        chapter_title = _extract_text(chapter_data.get("titre")) or f"Chapitre {chapter_number}"
        entries.append((f"chapter::{chapter_number}", f"Chapitre {chapter_number} - {chapter_title}"))
    if has_conclusion:
        entries.append(("conclusion", "Conclusion"))
    if has_postface:
        entries.append(("postface", "Postface"))
    return entries
