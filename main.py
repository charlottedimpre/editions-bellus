from ollama import chat
from ollama import ChatResponse
from parser import parse_fiche_cadrage, parse_plan_detaille, parse_structure_chapitres, parse_introduction


def fiche_cadrage():
  sujet = input("Enter your value: ")
  print(sujet)

  response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
    {
      'role': 'user',
      'content': "Tu es un expert en conception éditoriale de livres non-fiction. À partir du sujet fourni, génère UNIQUEMENT une fiche de cadrage, sans introduction ni commentaire. Respecte EXACTEMENT ce format :"
                 "<fiche_cadrage>"
                 "<sujet>[Reformulation précise et éditoriale du sujet brut]</sujet>"
                 "<sommaire>"
                 "- Chapitre 1 : [titre]"
                 "- [Autant de chapitres que le sujet le justifie, entre 6 et 10]"
                 "</sommaire>"
                 ""
                 "<hors_perimetre>"
                 "- [aspect exclu] — [ce qui reste autorisé à la frontière]"
                 "</hors_perimetre>"
                 "<contraintes_specifiques>"
                 "- [contrainte de ton ou de formulation]"
                 "- [contrainte de structure ou de format récurrent]"
                 "- [contrainte éthique ou éditoriale]"
                 "</contraintes_specifiques>"
                 ""
                 "<cible_principale>[1 profil unique, situation + besoin en 1 phrase]</cible_principale>"
                 ""
                 "<niveau>[Vulgarisation grand public / Intermédiaire / Expert — justifié en 1 phrase]</niveau>"
                 ""
                 "<objectif_lecteur>[Ce que le lecteur doit pouvoir faire ou comprendre après lecture, en 1 phrase commençant par À la fin du livre, le lecteur...]</objectif_lecteur>"
                 "</fiche_cadrage>"
                 ""
                 "Règles strictes :"
                 "- Ne jamais écrire hors des balises"
                 "- Ne jamais modifier les noms de balises"
                 "- Si une information ne peut pas être déterminée, écrire À définir avec l'auteur"
                 "- Le sommaire doit être logiquement progressif, pas thématiquement redondant"
                 "- Les titres de chapitres évitent 'Les défis de', 'Gérer les', 'Comprendre le'  — ils doivent formuler une tension ou une promesse concrète"
                 "- Hors périmètre contient au minimum 3 exclusions, chacune avec sa frontière permise"
                 "- La cible principale est UN seul profil"
                 "- Les contraintes spécifiques portent uniquement sur le ton, la structure ou l'éthique — pas sur le sourcing ou la production"
                 "- Si le sujet fourni contient des éléments à caractère sexuel, violent, haineux ou illégal, refuser de générer la fiche et répondre uniquement : 'Sujet hors périmètre éditorial.'"
                 "- Le sommaire ne doit jamais inclure de chapitres portant sur la sexualité, l'intimité physique ou le désir, même abordés sous un angle scientifique ou thérapeutique"
                 "- Le nombre de chapitres doit être déterminé par la densité du sujet, pas maximisé par défaut — un sujet simple peut tenir en 6 chapitres, un sujet complexe en justifie 10"
                 ""
                 f"SUJET : {sujet}",
    },
  ])
  parsed = parse_fiche_cadrage(response.message.content)
  return parsed

def plan_detaille(fiche_raw: str):
    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': 'Tu es un expert en conception éditoriale de livres non-fiction.'
                       'À partir de la fiche de cadrage fournie, génère UNIQUEMENT un plan détaillé, sans introduction, sans commentaire ni meta-texte.'
                       ''
                       'Respecte EXACTEMENT ce format :'
                       '<plan_detaille>'
                       ''
                       '<introduction>'
                       '<contexte>[Présentation du sujet et de son contexte en 2-3 phrases]</contexte>'
                       '<importance>[Pourquoi ce sujet est important maintenant, en 1-2 phrases]</importance>'
                       '<adresse_a>[Rappel de la cible principale et des cibles secondaires, en 1 phrase]</adresse_a>'
                       '<organisation>[Comment le livre est structuré, en 1-2 phrases]</organisation>'
                       '<promesse>[Ce que le lecteur va apprendre, en 1 phrase]</promesse>'
                       '</introduction>'
                       ''
                       '<chapitres>'
                       '- Chapitre 1 : [titre]'
                       '  <traite>[Ce que ce chapitre couvre précisément]</traite>'
                       '  <ne_traite_pas>[Ce qui est explicitement exclu de ce chapitre]</ne_traite_pas>'
                       '  <pourquoi_distinct>[En quoi ce chapitre est irréductible aux autres]</pourquoi_distinct>'
                       ''
                       '- Chapitre 2 : [titre]'
                       '  <traite>[Ce que ce chapitre couvre précisément]</traite>'
                       '  <ne_traite_pas>[Ce qui est explicitement exclu de ce chapitre]</ne_traite_pas>'
                       '  <pourquoi_distinct>[En quoi ce chapitre est irréductible aux autres]</pourquoi_distinct>'
                       ''
                       '- [Autant de chapitres que le sujet le justifie, entre 6 et 10]'
                       '</chapitres>'
                       ''
                       '<conclusion>'
                       '<synthese>[Résumé du parcours global sans répéter mot pour mot le contenu]</synthese>'
                       '<logique_ensemble>[La progression intellectuelle ou émotionnelle du livre en 1-2 phrases]</logique_ensemble>'
                       '<prochaines_etapes>[Ce que le lecteur est invité à faire après la lecture]</prochaines_etapes>'
                       '</conclusion>'
                       ''
                       '<exemple_fil_rouge>'
                       '<personnage>[Description du cas ou profil fictif utilisé comme exemple récurrent]</personnage>'
                       '<situation_depart>[Situation initiale de cet exemple au début du livre]</situation_depart>'
                       '<evolution>[Comment cet exemple évolue au fil des chapitres, en 2-3 phrases]</evolution>'
                       '</exemple_fil_rouge>'
                       ''
                       '</plan_detaille>'
                       ''
                       'Règles strictes :'
                       '- Ne jamais écrire hors des balises'
                       '- Ne jamais modifier les noms de balises'
                       '- Si une information ne peut pas être déterminée, écrire "À définir avec l\'auteur"'
                       '- Les titres de chapitres reprennent ceux définis dans <sommaire> sans modification'
                       '- Le nombre de chapitres doit être déterminé par la densité du sujet, pas maximisé par défaut'
                       '- Chaque chapitre doit passer le test de fusion : si deux chapitres peuvent être fusionnés sans perte, le plan est invalide — les reformuler ou les fusionner'
                       '- L\'introduction ne doit pas être marketing ou vague — chaque balise doit contenir une information concrète et spécifique au sujet'
                       '- La conclusion ne répète pas mot pour mot le contenu des chapitres'
                       '- Le sommaire ne doit jamais inclure de chapitres portant sur la sexualité, l\'intimité physique ou le désir, même abordés sous un angle scientifique ou thérapeutique'
                       '- L\'exemple fil rouge doit être anonymisé et composite (pas un cas réel unique)'
                       ''
                       'FICHE DE CADRAGE :'
                       f'{fiche_raw}',
        },
    ])
    parsed = parse_plan_detaille(response.message.content)
    return parsed

def structure_chapitre(fiche_raw: str, plan_raw: str):
    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': 'Tu es un expert en conception éditoriale de livres non-fiction.'
                       ''
                       'À partir de la fiche de cadrage et du plan détaillé fournis, génère UNIQUEMENT les fiches de structure pour chaque chapitre, sans introduction ni commentaire.'
                       'Répète ce bloc pour chaque chapitre :'
                       ''
                       '<chapitre_structure numero="[N]" titre="[titre exact du chapitre]">'
                       '  <section numero="1">'
                       '    <titre_section>[Titre de la section, formulé comme une tension ou une promesse]</titre_section>'
                       '    <objectif>[Ce que le lecteur comprend ou sait faire après cette section, en 1 phrase]</objectif>'
                       '    <concept_cle>[Le concept central de cette section, défini en 15 mots max]</concept_cle>'
                       '    <exemple>[Référence à l\'exemple fil rouge ou cas concret anonymisé]</exemple>'
                       '    <limite>[Ce que cette section n\'aborde pas, pour éviter le chevauchement]</limite>'
                       '    <mots_cible>[Nombre de mots estimé pour cette section, ex: 400-600]</mots_cible>'
                       '  </section>'
                       ''
                       '  <section numero="2">'
                       '    [même structure]'
                       '  </section>'
                       ''
                       '  [3 à 5 sections par chapitre]'
                       ''
                       '  <total_mots_chapitre>[Somme des mots cible des sections]</total_mots_chapitre>'
                       ''
                       '</chapitre_structure>'
                       ''
                       'Règles strictes :'
                       '- Ne jamais écrire hors des balises'
                       '- Ne jamais modifier les noms de balises'
                       '- Si une information ne peut pas être déterminée, écrire "À définir avec l\'auteur"'
                       '- Chaque chapitre contient entre 3 et 5 sections'
                       '- Les titres de sections évitent les formulations vagues ("Introduction à...", "Présentation de...", "Aperçu de...") — ils formulent une tension ou une promesse'
                       '- Deux sections ne peuvent pas avoir le même objectif — si c\'est le cas, les fusionner'
                       '- La limite de chaque section doit pointer explicitement vers la section ou le chapitre qui traite ce qui est exclu'
                       '- Les mots cible par section sont entre 300 et 800 mots'
                       '- Le total par chapitre ne dépasse pas 4000 mots'
                       '- Aucune référence à la sexualité, l\'intimité physique ou le désir'
                       ''
                       'FICHE DE CADRAGE :'
                       f'{fiche_raw}'
                       ''
                       'PLAN DÉTAILLÉ :'
                       f'{plan_raw}',
        },
    ])

    parsed = parse_structure_chapitres(response.message.content)
    return parsed

def gen_intro(fiche_raw: str, plan_raw: str):
    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': 'Tu es un expert en rédaction de livres non-fiction.'
                       'À partir de la fiche de cadrage et du plan détaillé fournis, rédige UNIQUEMENT l\'introduction du livre, sans commentaire ni meta-texte.'
                       'Contraintes de rédaction :'
                       '- Longueur : 2000 à 4000 mots'
                       '- Ne jamais dépasser 4000 mots'
                       '- Respecte strictement le contenu défini dans <introduction> du plan détaillé'
                       '- L\'ordre de rédaction suit obligatoirement :'
                       '  1. Contexte du sujet'
                       '  2. Pourquoi ce sujet est important'
                       '  3. À qui s\'adresse le livre'
                       '  4. Comment il est organisé'
                       '  5. Ce que le lecteur va apprendre'
                       ''
                       'Règles de style :'
                       '- Ton ancré dans <registre_ecriture> si défini, sinon : chaleureux et direct'
                       '- Pas de formulations marketing vagues ("Ce livre va changer votre vie...")'
                       '- Pas de questions rhétoriques en ouverture'
                       '- Chaque paragraphe apporte une information concrète et spécifique au sujet'
                       '- L\'exemple fil rouge à utiliser est UNIQUEMENT celui défini dans <exemple_fil_rouge> du plan détaillé — ne jamais créer un nouvel exemple, un nouveau personnage ou un nouveau cas, même partiellement différent'
                       '- Si <exemple_fil_rouge> n\'est pas fourni, écrire "À définir avec l\'auteur" et ne pas inventer de substitut'
                       '- Pas de jargon médical sans définition immédiate'
                       '- Vérifier la cohérence grammaticale avant de finaliser'
                       '- Rédiger exclusivement en français'
                       ''
                       'Interdit :'
                       '- Écrire hors du périmètre défini dans <hors_perimetre>'
                       '- Anticiper le contenu des chapitres au-delà d\'une phrase de présentation'
                       '- Toute référence à la sexualité, l\'intimité physique ou le désir'
                       '- Conclure l\'introduction par une promesse irréaliste ou non vérifiable'
                       ''
                       'FICHE DE CADRAGE :'
                       f'{fiche_raw}'
                       ''
                       'PLAN DÉTAILLÉ :'
                       f'{plan_raw}',
        },
    ])
    parsed = parse_introduction(response.message.content)
    return parsed

def gen_section(fiche_raw: str, plan_raw: str, structure_raw: list, chapitre_num: int, section_num: int):
    response: ChatResponse = chat(model='kimi-k2.5:cloud', messages=[
        {
            'role': 'user',
            'content': 'Tu es un expert en rédaction de livres non-fiction en langue française.'
                       'À partir de la fiche de cadrage, du plan détaillé et de la fiche de structure du chapitre fournis, rédige UNIQUEMENT le contenu de la section demandée, sans introduction ni commentaire.'
                       ''
                       'Contraintes de rédaction :'
                       '- Longueur cible : 50 à 100 mots'
                       '- Si <total_mots_chapitre> de la fiche de structure est inférieur à 50, développer chaque section pour atteindre 50 mots minimum en approfondissant les explications et les nuances — sans ajouter de nouvelles sections'
                       '- La contrainte de longueur du prompt prévaut toujours sur <total_mots_chapitre>'
                       '- Respecte strictement les sections définies dans <chapitre_structure>'
                       '- Chaque section suit l\'ordre : <titre_section>, <objectif>, <concept_cle>'
                       '- Ne pas introduire de sections absentes de <chapitre_structure>'
                       ''
                       'Règles de style :'
                       '- Rédiger exclusivement en français'
                       '- Interdire tout anglicisme, même courant ou technique (ex : "time-out" →  "pause", "time-blocking" → "découpage du temps en blocs", "feedback" → "retour immédiat") — toujours chercher l\'équivalent français avant d\'utiliser un terme étranger'
                       '- Ton ancré dans les contraintes définies dans <contraintes_specifiques>'
                       '- Pas de formulations marketing vagues'
                       '- Pas de questions rhétoriques en ouverture de section'
                       '- Chaque paragraphe apporte une information concrète et spécifique'
                       '- Ne pas créer de scénario, mise en situation ou exemple narratif en ouverture de chapitre — commencer directement par le contenu de la première section'
                       '- Ne jamais utiliser de mise en forme Markdown (gras, italique, titres, listes à puces, tirets) — rédiger en prose continue uniquement'
                       ''
                       'Interdit :'
                       '- Écrire hors du périmètre défini dans <hors_perimetre>'
                       '- Anticiper le contenu des chapitres suivants au-delà d\'une phrase de transition'
                       '- Toute référence à la sexualité, l\'intimité physique ou le désir'
                       '- Répéter le contenu d\'un chapitre précédent au-delà d\'une phrase de rappel'
                       '- Tout anglicisme ou terme étranger sans équivalent français explicite'
                       '- Aucun exemple narratif, scénario, mise en situation ou cas concret nulle part dans le chapitre — ni en ouverture, ni dans le corps du texte, ni en clôture de section'
                       '- Ne pas introduire l\'exemple fil rouge — il sera ajouté ultérieurement'
                       '- Ne pas inventer de personnage, situation fictive ou cas anonymisé en remplacement, même à titre illustratif'
                       '- Les concepts sont expliqués uniquement par des formulations analytiques, des mécanismes décrits et des données factuelles — jamais par des histoires'
                       '- Ne pas ajouter de checklist, résumé, points clés, exercice ou tout élément récapitulatif en fin de chapitre'
                       '- Le chapitre se termine à la dernière phrase de la dernière section, sans aucun ajout'
                       ''
                       'FICHE DE CADRAGE :'
                       f'{fiche_raw}'
                       ''
                       'PLAN DÉTAILLÉ :'
                       f'{plan_raw}'
                       ''
                       'FICHE DE STRUCTURE DU CHAPITRE :'
                       f'{structure_raw}'
                       ''
                       f'CHAPITRE À RÉDIGER : Chapitre {chapitre_num}'
                       f'SECTION À RÉDIGER : Section {section_num}',
        },
    ])
    print(response['message']['content'])

def gen_livre(fiche_raw: str, plan_raw: str, structure_raw: list):
    for chap in structure_raw:
        print(f"Chapitre : {chap['numero']} — {chap['titre']}")
        for sec in chap['sections']:
            gen_section(fiche_raw, plan_raw, structure_raw, chap['numero'], sec['numero'])

def main():
  fiche = fiche_cadrage()
  print(f"Fiche de cadrage générée : {fiche['nbre_chapitres']} chapitres")

  plan = plan_detaille(fiche["_raw"])
  print(f"Plan détaillé généré : {len(plan['chapitres'])} chapitres")

  structure = structure_chapitre(fiche["_raw"], plan["_raw"])
  print(f"Structure générée : {len(structure)} chapitres")

  for chap in structure:
      print(f"  Chapitre {chap['numero']} — {chap['titre']} ({chap['total_mots_chapitre']} mots, {len(chap['sections'])} sections)")

  intro = gen_intro(fiche["_raw"], plan["_raw"])
  print(intro["intro"])

  gen_livre(fiche["_raw"], plan["_raw"], structure)


if __name__ == "__main__":  main()