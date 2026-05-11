from typing import List
from .fiche_stategique import recup_fiche_strat
from .recherches import recup_recherches
from .infos import recup_infos
from .plan import recup_chapitres, recup_sections

model = "kimi-k2.5:cloud"

def recup_fichiers(fichiers_a_recup : List):
    fichiers_renvoyes : List = []
    for fichier in fichiers_a_recup:
        if fichier in fichiers_a_recup:
            if fichier == "fiche_strategique":
                fichiers_renvoyes.append(recup_fiche_strat())
            if fichier == "recherches":
                recherches = recup_recherches()
                for recherche in recherches:
                    fichiers_renvoyes.append(recherche)
            if fichier == "plan":
                fichiers_renvoyes.append(recup_chapitres())
                fichiers_renvoyes.append(recup_sections())
            if fichier == "infos":
                infos = recup_infos()
                for info in infos:
                    fichiers_renvoyes.append(info)


    return fichiers_renvoyes