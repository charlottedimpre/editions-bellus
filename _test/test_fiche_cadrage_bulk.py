import os
from datetime import datetime

from ollama import chat
from ollama import ChatResponse
from parser import parse_fiche_cadrage, parse_plan_detaille, parse_structure_chapitres, parse_introduction

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


def fiche_cadrage(sujet: str, niveau: str):
  print(sujet)
  input_path = os.path.join("input", "fiche_cadrage", f"{niveau}.txt")

  with open(input_path, "r", encoding="utf-8") as f:
    prompt_template = f.read()

  response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
    {
      'role': 'user',
      'content': f'{prompt_template}\n\nSUJET : {sujet}',
    },
  ])
  parsed = parse_fiche_cadrage(response.message.content)
  return parsed

if __name__ == '__main__':
    niveau = ["Débutant", "Intermédiaire", "Avancé"]
    fichier = ["fc_debutant", "fc_intermediaire", "fc_avance"]

    """
    sujet = ["Investir dans les immeubles de rapport en France", "Structurer un immeuble de rapport rentable étape par étape", "Vivre avec un adulte TDAH au quotidien", "Gérer un bien locatif en mono-propriété"]

    
    for i in range(len(sujet)):
        for j in range(len(niveau)):
            filepath = os.path.join(OUTPUT_DIR, f"fichecadre{i}{j}_{timestamp}.txt")
            fiche = fiche_cadrage(sujet[i], niveau[j])
            print(f"Fiche de cadrage générée : {sujet[i]} - {niveau[j]}")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("FICHE DE CADRAGE\n")
                f.write("=" * 60 + "\n")
                f.write(fiche["_raw"] + "\n\n")
    """

    sujet = input("Quel est le sujet de votre livre ? ")
    while len(sujet) < 1:
        print("Le sujet ne peut pas être vide.")
        sujet = input("Quel est le sujet de votre livre ? ")

    niveau_input = input("Quel niveau souhaitez-vous ? (1 - Débutant, 2 - Intermédiaire, 3 - Avancé) : ")

    while niveau_input not in ['1', '2', '3']:
        print("Le niveau doit être 1, 2 ou 3.")
        niveau_input = input("Quel niveau souhaitez-vous ? (1 - Débutant, 2 - Intermédiaire, 3 - Avancé) : ")


    filepath = os.path.join(OUTPUT_DIR, "fichecadre.txt")
    fiche = fiche_cadrage(sujet, fichier[int(niveau_input)-1])
    print(f"Fiche de cadrage générée : {sujet} {niveau[int(niveau_input)-1]}")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(fiche["_raw"])

