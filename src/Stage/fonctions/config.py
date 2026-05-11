from ..models import Variables

def recup_nb_chapitres():
    return Variables.objects.last().nb_chapitre

def recup_nb_mots_cibles():
    return Variables.objects.last().nb_mots_cible

def recup_fourchette_mots_ratio():
    return False