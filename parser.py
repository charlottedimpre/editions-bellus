import json
import re
from pathlib import Path
from typing import Optional, Union


def _collapse_newlines(s: Optional[str]) -> Optional[str]:
    """
    Remplace les sauts de ligne par des espaces et supprime les espaces multiples.
    """
    if s is None:
        return None
    return re.sub(r"\s+", " ", s).strip()


def extract_tag(text: str, tag_name: str) -> Optional[str]:
    """
    Extrait le contenu entre <tag_name> et </tag_name>.
    Retourne None si la balise n'est pas trouvée.

    >>> extract_tag("<sujet>Mon sujet</sujet>", "sujet")
    'Mon sujet'
    """
    pattern = rf"<{re.escape(tag_name)}>(.*?)</{re.escape(tag_name)}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_all_tags(text: str, tag_name: str) -> list[str]:
    """
    Extrait tous les contenus entre <tag_name> et </tag_name>.
    Utile pour les balises répétées (ex: plusieurs <section>).

    >>> extract_all_tags("<a>1</a><a>2</a>", "a")
    ['1', '2']
    """
    pattern = rf"<{re.escape(tag_name)}>(.*?)</{re.escape(tag_name)}>"
    return [m.strip() for m in re.findall(pattern, text, re.DOTALL)]


def extract_tag_with_attrs(text: str, tag_name: str) -> list[dict]:
    """
    Extrait les balises avec attributs, ex:
    <chapitre_structure numero="1" titre="Mon titre">contenu</chapitre_structure>

    Retourne une liste de dicts: [{"attrs": {"numero": "1", ...}, "content": "..."}]
    """
    # Capture la balise ouvrante avec attributs + contenu + balise fermante
    pattern = rf"<{re.escape(tag_name)}\s+(.*?)>(.*?)</{re.escape(tag_name)}>"
    results = []
    for match in re.finditer(pattern, text, re.DOTALL):
        attrs_str = match.group(1)
        content = match.group(2).strip()
        # Parser les attributs key="value"
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', attrs_str))
        results.append({"attrs": attrs, "content": content})
    return results



# ---------------------------------------------------------------------------
# Parsers de haut niveau pour chaque étape
# ---------------------------------------------------------------------------

def parse_fiche_cadrage(text: str) -> dict:
    """
    Parse la réponse de l'étape 1 (fiche de cadrage).
    """
    fiche = extract_tag(text, "fiche_cadrage") or text

    # Extraire les chapitres du sommaire
    sommaire_raw = extract_tag(fiche, "sommaire") or ""
    chapitres = re.findall(r"-\s*Chapitre\s+\d+\s*:\s*(.+)", sommaire_raw)

    # Extraire les exclusions du hors périmètre
    hp_raw = extract_tag(fiche, "hors_perimetre") or ""
    exclusions = [line.strip("- ").strip() for line in hp_raw.splitlines() if line.strip().startswith("-")]

    # Extraire les contraintes
    cs_raw = extract_tag(fiche, "contraintes_specifiques") or ""
    contraintes = [line.strip("- ").strip() for line in cs_raw.splitlines() if line.strip().startswith("-")]

    return {
        "sujet": extract_tag(fiche, "sujet"),
        "sommaire": chapitres,
        "hors_perimetre": exclusions,
        "contraintes_specifiques": contraintes,
        "cible_principale": extract_tag(fiche, "cible_principale"),
        "niveau": extract_tag(fiche, "niveau"),
        "objectif_lecteur": extract_tag(fiche, "objectif_lecteur"),
        "nbre_chapitres": len(chapitres),
        "_raw": text,
    }


def parse_plan_detaille(text: str) -> dict:
    """
    Parse la réponse de l'étape 2 (plan détaillé).
    """
    plan = extract_tag(text, "plan_detaille") or text

    # Introduction
    intro = {
        "contexte": extract_tag(plan, "contexte"),
        "importance": extract_tag(plan, "importance"),
        "adresse_a": extract_tag(plan, "adresse_a"),
        "organisation": extract_tag(plan, "organisation"),
        "promesse": extract_tag(plan, "promesse"),
    }

    # Chapitres
    chapitres_raw = extract_tag(plan, "chapitres") or ""
    # Découper par "- Chapitre N :"
    chapitre_blocks = re.split(r"(?=- Chapitre\s+\d+\s*:)", chapitres_raw)
    chapitres = []
    for block in chapitre_blocks:
        block = block.strip()
        if not block:
            continue
        titre_match = re.match(r"-\s*Chapitre\s+(\d+)\s*:\s*(.+?)(?:\n|$)", block)
        if titre_match:
            chapitres.append({
                "numero": int(titre_match.group(1)),
                "titre": titre_match.group(2).strip(),
                "traite": extract_tag(block, "traite"),
                "ne_traite_pas": extract_tag(block, "ne_traite_pas"),
                "pourquoi_distinct": extract_tag(block, "pourquoi_distinct"),
            })

    # Conclusion
    conclusion = {
        "synthese": extract_tag(plan, "synthese"),
        "logique_ensemble": extract_tag(plan, "logique_ensemble"),
        "prochaines_etapes": extract_tag(plan, "prochaines_etapes"),
    }

    # Exemple fil rouge
    fil_rouge = {
        "personnage": extract_tag(plan, "personnage"),
        "situation_depart": extract_tag(plan, "situation_depart"),
        "evolution": extract_tag(plan, "evolution"),
    }

    return {
        "introduction": intro,
        "chapitres": chapitres,
        "conclusion": conclusion,
        "exemple_fil_rouge": fil_rouge,
        "_raw": text,
    }


def parse_structure_chapitres(text: str) -> list[dict]:
    """
    Parse la réponse de l'étape 3 (fiches de structure des chapitres).
    """
    blocs = extract_tag_with_attrs(text, "chapitre_structure")
    chapitres = []

    for bloc in blocs:
        # Sections
        section_blocs = extract_tag_with_attrs(bloc["content"], "section")
        sections = []

        for sb in section_blocs:
            sections.append({
                "numero": sb["attrs"].get("numero"),
                "titre_section": extract_tag(sb["content"], "titre_section"),
                "objectif": extract_tag(sb["content"], "objectif"),
                "concept_cle": extract_tag(sb["content"], "concept_cle"),
                "exemple": extract_tag(sb["content"], "exemple"),
                "limite": extract_tag(sb["content"], "limite"),
                "mots_cible": extract_tag(sb["content"], "mots_cible"),
            })

        # Fallback : si les sections n'ont pas d'attributs, essayer sans attributs
        if not sections:
            section_contents = extract_all_tags(bloc["content"], "section")
            for i, sc in enumerate(section_contents, 1):
                sections.append({
                    "numero": str(i),
                    "titre_section": extract_tag(sc, "titre_section"),
                    "objectif": extract_tag(sc, "objectif"),
                    "concept_cle": extract_tag(sc, "concept_cle"),
                    "exemple": extract_tag(sc, "exemple"),
                    "limite": extract_tag(sc, "limite"),
                    "mots_cible": extract_tag(sc, "mots_cible"),
                })

        chapitres.append({
            "numero": bloc["attrs"].get("numero"),
            "titre": bloc["attrs"].get("titre"),
            "sections": sections,
            "total_mots_chapitre": extract_tag(bloc["content"], "total_mots_chapitre"),
        })

    return chapitres


def parse_introduction(text: str) -> dict:
    """
    Parse la réponse de l'étape 4 (rédaction de l'introduction).
    """
    intro = extract_tag(text, "introduction") or text
    return {
        "intro": _collapse_newlines(intro),
        "_raw": text,
    }


def parse_section(text: str, chapitre: int, section: int) -> dict:
    """
    Parse la réponse de la rédaction d'une section.
    Retourne un dict avec le numéro de chapitre, de section et le contenu.
    """
    contenu = extract_tag(text, "section") or text
    return {
        "chapitre": chapitre,
        "section": section,
        "contenu": _collapse_newlines(contenu.strip()),
    }


# ---------------------------------------------------------------------------
# Export JSON
# ---------------------------------------------------------------------------

def to_json(data: Union[dict, list], indent: int = 2) -> str:
    """
    Sérialise un résultat parsé (dict ou list) en chaîne JSON.

    >>> to_json({"sujet": "Test"})
    '{\\n  "sujet": "Test"\\n}'
    """
    return json.dumps(data, ensure_ascii=False, indent=indent)


def to_json_file(data: Union[dict, list], path: Union[str, Path], indent: int = 2) -> Path:
    """
    Écrit un résultat parsé dans un fichier JSON.
    Crée les dossiers parents si nécessaire.
    Retourne le Path du fichier créé.

    >>> import tempfile, os
    >>> p = to_json_file({"sujet": "Test"}, os.path.join(tempfile.gettempdir(), "test.json"))
    >>> p.exists()
    True
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Extraction de blocs XML bruts
# ---------------------------------------------------------------------------

def extract_xml_block(text: str, tag_name: str) -> Optional[str]:
    """
    Extrait un bloc XML complet (balise ouvrante + contenu + balise fermante)
    sans le parser. Retourne None si la balise n'est pas trouvée.

    >>> extract_xml_block("<root><sujet>Mon sujet</sujet></root>", "sujet")
    '<sujet>Mon sujet</sujet>'
    """
    pattern = rf"(<{re.escape(tag_name)}(?:\s[^>]*)?>.*?</{re.escape(tag_name)}>)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_all_xml_blocks(text: str, tag_name: str) -> list[str]:
    """
    Extrait tous les blocs XML complets pour une balise donnée,
    avec balises incluses.

    >>> extract_all_xml_blocks("<a>1</a><a>2</a>", "a")
    ['<a>1</a>', '<a>2</a>']
    """
    pattern = rf"(<{re.escape(tag_name)}(?:\s[^>]*)?>.*?</{re.escape(tag_name)}>)"
    return [m.strip() for m in re.findall(pattern, text, re.DOTALL)]


