"""
Cas d'usage de toutes les fonctions du module parser.
Exécuter avec : python _test/test_parser_demo.py
"""

import os
import sys
import json

# Permettre l'import depuis la racine du projet
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parser import (
    extract_tag,
    extract_all_tags,
    extract_tag_with_attrs,
    parse_fiche_cadrage,
    parse_plan_detaille,
    parse_structure_chapitres,
    parse_introduction,
    to_json,
    to_json_file,
    extract_xml_block,
    extract_all_xml_blocks,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "demo")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# Données de test réalistes (simulent les réponses LLM)
# ═══════════════════════════════════════════════════════════════════════════

FICHE_CADRAGE_RAW = """<fiche_cadrage>
<sujet>Optimiser sa consommation de caféine : mécanismes, bénéfices et risques pour une performance durable</sujet>
<sommaire>
- Chapitre 1 : La caféine dans le corps humain
- Chapitre 2 : Les sources de caféine au quotidien
- Chapitre 3 : Performance cognitive et physique
- Chapitre 4 : Les effets indésirables et la dépendance
- Chapitre 5 : Chronobiologie et timing optimal
- Chapitre 6 : Populations sensibles et contre-indications
- Chapitre 7 : Stratégies de réduction progressive
- Chapitre 8 : Alternatives et synergies nutritionnelles
</sommaire>
<hors_perimetre>
- Les protocoles de sevrage médicalisé — rediriger vers un professionnel de santé pour les cas de dépendance sévère
- Les dosages thérapeutiques en milieu hospitalier — exclure les applications cliniques spécialisées
- Les innovations récentes non validées scientifiquement — limiter aux données consolidées
</hors_perimetre>
<contraintes_specifiques>
- Le ton doit rester pédagogique et rigoureux
- Mention des risques pour chaque bénéfice présenté
- Préciser que le livre ne remplace pas un avis médical
</contraintes_specifiques>
<cible_principale>Un professionnel ou un étudiant cherchant à optimiser sa vigilance et sa productivité sans compromettre sa santé</cible_principale>
<niveau>Avancé — suppose une familiarité avec les principes de base de la nutrition et du métabolisme</niveau>
<objectif_lecteur>À la fin du livre, le lecteur saura ajuster sa consommation de caféine en fonction de ses objectifs, de son chronotype et de sa tolérance individuelle</objectif_lecteur>
</fiche_cadrage>"""

PLAN_DETAILLE_RAW = """<plan_detaille>
<introduction>
<contexte>La caféine est la substance psychoactive la plus consommée au monde, présente dans le café, le thé et de nombreuses boissons industrielles.</contexte>
<importance>Face à l'augmentation des exigences cognitives dans le monde professionnel, comprendre les mécanismes de la caféine devient un enjeu de santé publique.</importance>
<adresse_a>Ce livre s'adresse aux professionnels et étudiants souhaitant optimiser leur consommation de caféine de manière éclairée.</adresse_a>
<organisation>L'ouvrage est organisé en huit chapitres progressifs, des mécanismes biologiques aux stratégies d'optimisation.</organisation>
<promesse>Le lecteur disposera d'une grille de lecture scientifique pour adapter sa consommation à son profil.</promesse>
</introduction>

<chapitres>
- Chapitre 1 : La caféine dans le corps humain
  <traite>Les mécanismes d'absorption, de métabolisation hépatique et d'action sur les récepteurs à adénosine.</traite>
  <ne_traite_pas>Les détails pharmacologiques de niveau doctoral ou les interactions médicamenteuses complexes.</ne_traite_pas>
  <pourquoi_distinct>Ce chapitre pose le socle biologique sans lequel les chapitres suivants ne sont pas compréhensibles.</pourquoi_distinct>

- Chapitre 2 : Les sources de caféine au quotidien
  <traite>La teneur en caféine des principales boissons et aliments, les variabilités selon la préparation.</traite>
  <ne_traite_pas>Les recettes de préparation ni les aspects culturels ou historiques du café.</ne_traite_pas>
  <pourquoi_distinct>Ce chapitre cartographie les apports réels, là où le chapitre 1 explique le mécanisme.</pourquoi_distinct>

- Chapitre 3 : Performance cognitive et physique
  <traite>Les effets mesurés de la caféine sur la vigilance, la mémoire, le temps de réaction et l'endurance.</traite>
  <ne_traite_pas>Les protocoles de dopage sportif ou les usages en compétition réglementée.</ne_traite_pas>
  <pourquoi_distinct>Ce chapitre traite exclusivement des bénéfices, avant d'aborder les risques au chapitre 4.</pourquoi_distinct>
</chapitres>

<conclusion>
<synthese>Le parcours va des mécanismes biologiques aux stratégies concrètes d'optimisation.</synthese>
<logique_ensemble>Le livre construit une compréhension progressive : comprendre, cartographier, optimiser, ajuster.</logique_ensemble>
<prochaines_etapes>Le lecteur est invité à tenir un journal de consommation pendant 4 semaines pour affiner son profil.</prochaines_etapes>
</conclusion>

<exemple_fil_rouge>
<personnage>Alex, 34 ans, développeur logiciel, consomme 5 à 6 cafés par jour depuis 10 ans.</personnage>
<situation_depart>Alex souffre d'insomnies chroniques et de baisses de concentration en fin de matinée malgré sa consommation élevée.</situation_depart>
<evolution>Au fil des chapitres, Alex découvre sa tolérance, ajuste ses horaires de consommation et réduit progressivement à 3 cafés ciblés.</evolution>
</exemple_fil_rouge>
</plan_detaille>"""

STRUCTURE_CHAPITRES_RAW = """<chapitre_structure numero="1" titre="La caféine dans le corps humain">
  <section numero="1">
    <titre_section>L'adénosine, ce signal de fatigue que la caféine détourne</titre_section>
    <objectif>Le lecteur comprend le mécanisme biologique fondamental de la caféine</objectif>
    <concept_cle>Blocage des récepteurs à adénosine par la caféine</concept_cle>
    <exemple>Alex ne comprend pas pourquoi son cinquième café ne fait plus effet</exemple>
    <limite>Ne traite pas de la tolérance (chapitre 4)</limite>
    <mots_cible>400-600</mots_cible>
  </section>
  <section numero="2">
    <titre_section>Du premier café au pic plasmatique : le trajet de la molécule</titre_section>
    <objectif>Le lecteur connaît la cinétique d'absorption et le délai d'action de la caféine</objectif>
    <concept_cle>Absorption gastro-intestinale et pic plasmatique à 45 minutes</concept_cle>
    <exemple>Alex boit son café 5 minutes avant une réunion et ne ressent rien</exemple>
    <limite>Ne traite pas des variations génétiques (section 3)</limite>
    <mots_cible>400-500</mots_cible>
  </section>
  <section numero="3">
    <titre_section>Métaboliseurs rapides, métaboliseurs lents : la loterie génétique</titre_section>
    <objectif>Le lecteur identifie son profil métabolique probable</objectif>
    <concept_cle>Polymorphisme du gène CYP1A2 et demi-vie variable</concept_cle>
    <exemple>Alex découvre que sa sensibilité a une composante génétique</exemple>
    <limite>Ne traite pas des tests génétiques commerciaux (hors périmètre)</limite>
    <mots_cible>500-700</mots_cible>
  </section>
  <total_mots_chapitre>1300-1800</total_mots_chapitre>
</chapitre_structure>

<chapitre_structure numero="2" titre="Les sources de caféine au quotidien">
  <section numero="1">
    <titre_section>Le café n'a pas le monopole : cartographie des sources cachées</titre_section>
    <objectif>Le lecteur identifie toutes les sources de caféine dans son alimentation</objectif>
    <concept_cle>Teneur en caféine variable selon la source et la préparation</concept_cle>
    <exemple>Alex réalise que son thé vert de l'après-midi contient aussi de la caféine</exemple>
    <limite>Ne traite pas des effets (chapitre 3)</limite>
    <mots_cible>500-600</mots_cible>
  </section>
  <section numero="2">
    <titre_section>Espresso, filtre, instantané : décoder les étiquettes</titre_section>
    <objectif>Le lecteur sait comparer les dosages réels entre types de café</objectif>
    <concept_cle>Un espresso contient moins de caféine qu'un café filtre de 250 ml</concept_cle>
    <exemple>Alex pensait que l'espresso était le plus fort — il avait tort</exemple>
    <limite>Ne traite pas des recettes de préparation (hors périmètre)</limite>
    <mots_cible>400-500</mots_cible>
  </section>
  <total_mots_chapitre>900-1100</total_mots_chapitre>
</chapitre_structure>"""

INTRODUCTION_RAW = """<introduction>
La caféine accompagne l'humanité depuis des siècles. Présente dans le café, le thé, le cacao
et de nombreuses boissons industrielles, elle est la substance psychoactive la plus consommée
au monde. Pourtant, rares sont ceux qui comprennent véritablement ses mécanismes d'action
et ses effets sur l'organisme.

Ce livre propose une approche scientifique et pragmatique de la consommation de caféine,
destinée à quiconque souhaite optimiser sa vigilance sans compromettre sa santé. Au fil de
huit chapitres, le lecteur découvrira les mécanismes biologiques, les sources réelles, les
bénéfices mesurés et les risques documentés de cette molécule omniprésente.
</introduction>"""


def sep(titre: str):
    """Affiche un séparateur visuel."""
    print(f"\n{'='*70}")
    print(f"  {titre}")
    print(f"{'='*70}\n")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Fonctions de bas niveau : extract_tag, extract_all_tags, extract_tag_with_attrs
# ═══════════════════════════════════════════════════════════════════════════

def demo_extract_tag():
    sep("extract_tag — Extraire le contenu d'une balise unique")

    sujet = extract_tag(FICHE_CADRAGE_RAW, "sujet")
    print(f"Sujet extrait : {sujet}")

    cible = extract_tag(FICHE_CADRAGE_RAW, "cible_principale")
    print(f"Cible principale : {cible}")

    # Balise inexistante → None
    inexistant = extract_tag(FICHE_CADRAGE_RAW, "balise_qui_nexiste_pas")
    print(f"Balise inexistante : {inexistant}")


def demo_extract_all_tags():
    sep("extract_all_tags — Extraire plusieurs occurrences d'une même balise")

    # Extraire tous les <traite> du plan détaillé
    traites = extract_all_tags(PLAN_DETAILLE_RAW, "traite")
    print(f"Nombre de balises <traite> trouvées : {len(traites)}")
    for i, t in enumerate(traites, 1):
        print(f"  [{i}] {t[:80]}...")

    # Extraire tous les <titre_section> de la structure
    titres = extract_all_tags(STRUCTURE_CHAPITRES_RAW, "titre_section")
    print(f"\nTitres de sections trouvés : {len(titres)}")
    for titre in titres:
        print(f"  → {titre}")


def demo_extract_tag_with_attrs():
    sep("extract_tag_with_attrs — Extraire des balises avec attributs")

    blocs = extract_tag_with_attrs(STRUCTURE_CHAPITRES_RAW, "chapitre_structure")
    print(f"Chapitres avec attributs trouvés : {len(blocs)}")
    for bloc in blocs:
        print(f"  Chapitre {bloc['attrs'].get('numero')} : {bloc['attrs'].get('titre')}")
        print(f"    Contenu (100 premiers car.) : {bloc['content'][:100].strip()}...")

    # Extraire les sections avec attributs
    sections = extract_tag_with_attrs(STRUCTURE_CHAPITRES_RAW, "section")
    print(f"\nSections avec attributs trouvées : {len(sections)}")
    for sec in sections:
        print(f"  Section {sec['attrs'].get('numero')} — {extract_tag(sec['content'], 'titre_section')}")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Parsers de haut niveau
# ═══════════════════════════════════════════════════════════════════════════

def demo_parse_fiche_cadrage():
    sep("parse_fiche_cadrage — Parser une fiche de cadrage complète")

    fiche = parse_fiche_cadrage(FICHE_CADRAGE_RAW)

    print(f"Sujet            : {fiche['sujet']}")
    print(f"Nombre chapitres : {fiche['nbre_chapitres']}")
    print(f"Cible            : {fiche['cible_principale']}")
    print(f"Niveau           : {fiche['niveau']}")
    print(f"Objectif lecteur : {fiche['objectif_lecteur']}")
    print(f"\nSommaire :")
    for i, ch in enumerate(fiche["sommaire"], 1):
        print(f"  {i}. {ch}")
    print(f"\nHors périmètre ({len(fiche['hors_perimetre'])} exclusions) :")
    for ex in fiche["hors_perimetre"]:
        print(f"  ✗ {ex}")
    print(f"\nContraintes ({len(fiche['contraintes_specifiques'])}) :")
    for c in fiche["contraintes_specifiques"]:
        print(f"  • {c}")

    return fiche


def demo_parse_plan_detaille():
    sep("parse_plan_detaille — Parser un plan détaillé")

    plan = parse_plan_detaille(PLAN_DETAILLE_RAW)

    print("Introduction :")
    for k, v in plan["introduction"].items():
        print(f"  {k:15s} : {v[:80] if v else '—'}...")

    print(f"\nChapitres ({len(plan['chapitres'])}) :")
    for ch in plan["chapitres"]:
        print(f"  Chapitre {ch['numero']} : {ch['titre']}")
        print(f"    Traite         : {ch['traite'][:60]}...")
        print(f"    Ne traite pas  : {ch['ne_traite_pas'][:60]}...")

    print(f"\nConclusion :")
    print(f"  Synthèse : {plan['conclusion']['synthese']}")

    print(f"\nFil rouge :")
    print(f"  Personnage : {plan['exemple_fil_rouge']['personnage']}")

    return plan


def demo_parse_structure_chapitres():
    sep("parse_structure_chapitres — Parser les fiches de structure")

    chapitres = parse_structure_chapitres(STRUCTURE_CHAPITRES_RAW)

    print(f"Chapitres structurés : {len(chapitres)}")
    for chap in chapitres:
        print(f"\n  Chapitre {chap['numero']} — {chap['titre']} ({chap['total_mots_chapitre']} mots)")
        for sec in chap["sections"]:
            print(f"    Section {sec['numero']} : {sec['titre_section']}")
            print(f"      Objectif    : {sec['objectif']}")
            print(f"      Concept clé : {sec['concept_cle']}")
            print(f"      Mots cible  : {sec['mots_cible']}")

    return chapitres


def demo_parse_introduction():
    sep("parse_introduction — Parser l'introduction rédigée")

    intro = parse_introduction(INTRODUCTION_RAW)

    print(f"Intro (collapse) : {intro['intro'][:120]}...")
    print(f"Raw  (longueur)  : {len(intro['_raw'])} caractères")

    return intro


# ═══════════════════════════════════════════════════════════════════════════
# 3. Export JSON
# ═══════════════════════════════════════════════════════════════════════════

def demo_to_json(fiche: dict):
    sep("to_json — Sérialiser un résultat en chaîne JSON")

    # Exclure _raw pour un export propre
    export = {k: v for k, v in fiche.items() if k != "_raw"}
    json_str = to_json(export)
    print(json_str[:500])
    if len(json_str) > 500:
        print(f"  ... ({len(json_str)} caractères au total)")


def demo_to_json_file(fiche: dict, plan: dict, chapitres: list):
    sep("to_json_file — Écrire les résultats dans des fichiers JSON")

    # Fiche de cadrage → JSON
    fiche_export = {k: v for k, v in fiche.items() if k != "_raw"}
    p1 = to_json_file(fiche_export, os.path.join(OUTPUT_DIR, "fiche_cadrage.json"))
    print(f"Fiche de cadrage  → {p1}")

    # Plan détaillé → JSON
    plan_export = {k: v for k, v in plan.items() if k != "_raw"}
    p2 = to_json_file(plan_export, os.path.join(OUTPUT_DIR, "plan_detaille.json"))
    print(f"Plan détaillé     → {p2}")

    # Structure chapitres → JSON
    p3 = to_json_file(chapitres, os.path.join(OUTPUT_DIR, "structure_chapitres.json"))
    print(f"Structure chap.   → {p3}")

    # Tout en un seul fichier
    tout = {
        "fiche_cadrage": fiche_export,
        "plan_detaille": plan_export,
        "structure_chapitres": chapitres,
    }
    p4 = to_json_file(tout, os.path.join(OUTPUT_DIR, "livre_complet.json"))
    print(f"Livre complet     → {p4}")

    # Vérification de relecture
    with open(p4, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    print(f"\nRelecture OK : {len(reloaded)} clés racine ({', '.join(reloaded.keys())})")


# ═══════════════════════════════════════════════════════════════════════════
# 4. Extraction de blocs XML bruts
# ═══════════════════════════════════════════════════════════════════════════

def demo_extract_xml_block():
    sep("extract_xml_block — Extraire un bloc XML brut (avec balises)")

    # Extraire le bloc <sommaire> complet
    bloc_sommaire = extract_xml_block(FICHE_CADRAGE_RAW, "sommaire")
    print("Bloc <sommaire> :")
    print(bloc_sommaire)

    # Extraire le bloc <exemple_fil_rouge> complet
    bloc_fil_rouge = extract_xml_block(PLAN_DETAILLE_RAW, "exemple_fil_rouge")
    print(f"\nBloc <exemple_fil_rouge> :")
    print(bloc_fil_rouge)

    # Balise inexistante → None
    bloc_vide = extract_xml_block(FICHE_CADRAGE_RAW, "inexistant")
    print(f"\nBloc inexistant : {bloc_vide}")


def demo_extract_all_xml_blocks():
    sep("extract_all_xml_blocks — Extraire tous les blocs XML d'un même type")

    # Tous les blocs <chapitre_structure>
    blocs_chapitres = extract_all_xml_blocks(STRUCTURE_CHAPITRES_RAW, "chapitre_structure")
    print(f"Blocs <chapitre_structure> trouvés : {len(blocs_chapitres)}")
    for i, bloc in enumerate(blocs_chapitres, 1):
        print(f"\n--- Bloc {i} (premiers 200 car.) ---")
        print(bloc[:200] + "...")

    # Tous les blocs <section>
    blocs_sections = extract_all_xml_blocks(STRUCTURE_CHAPITRES_RAW, "section")
    print(f"\n\nBlocs <section> trouvés : {len(blocs_sections)}")
    for i, bloc in enumerate(blocs_sections, 1):
        titre = extract_tag(bloc, "titre_section")
        print(f"  [{i}] {titre}")

    # Combiner XML brut + JSON : extraire un bloc puis le parser
    print("\n--- Combo : bloc XML brut → parse → JSON ---")
    premier_chapitre_xml = blocs_chapitres[0]
    print(f"XML brut ({len(premier_chapitre_xml)} car.) → ", end="")
    # On peut re-parser ce bloc isolé
    parsed = parse_structure_chapitres(premier_chapitre_xml)
    json_out = to_json(parsed[0] if parsed else {})
    print(f"JSON ({len(json_out)} car.)")
    print(json_out[:300])


# ═══════════════════════════════════════════════════════════════════════════
# Exécution
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║   DÉMONSTRATION — Toutes les fonctions du module parser              ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    # --- Bas niveau ---
    demo_extract_tag()
    demo_extract_all_tags()
    demo_extract_tag_with_attrs()

    # --- Parsers de haut niveau ---
    fiche = demo_parse_fiche_cadrage()
    plan = demo_parse_plan_detaille()
    chapitres = demo_parse_structure_chapitres()
    intro = demo_parse_introduction()

    # --- Export JSON ---
    demo_to_json(fiche)
    demo_to_json_file(fiche, plan, chapitres)

    # --- Blocs XML bruts ---
    demo_extract_xml_block()
    demo_extract_all_xml_blocks()

    sep("TERMINÉ")
    print(f"Fichiers JSON générés dans : {os.path.abspath(OUTPUT_DIR)}")
    print("Toutes les fonctions du parseur ont été démontrées avec succès.")

