from django.db import models


class FicheStrategique(models.Model):
    sujet_précis = models.TextField()
    cible = models.TextField()
    niveau = models.CharField(max_length=100)
    objectif_lecteur = models.TextField()
    logique_ordre_des_chapitres = models.TextField(default='chronologique')
    sujets_exclus_du_livre = models.TextField(null=True, blank=True)
    contraintes_éditoriales = models.TextField(null=True, blank=True)
    fiche_validée_par_humain = models.BooleanField(default=False)

    livre_id = models.IntegerField(null=True, blank=True )

    class Meta:
        db_table = 'fiche_strategique'


class Chapitre(models.Model):
    ROLE_CHOICES = [
        ('introduction', 'Introduction'),
        ('développement', 'Développement'),
        ('conclusion', 'Conclusion'),
    ]
    STATUT_CHOICES = [
        ('à_rédiger', 'À rédiger'),
        ('en_cours', 'En cours'),
        ('rédigé', 'Rédigé'),
        ('validé', 'Validé'),
    ]
    ordre = models.IntegerField(unique=True)
    titre = models.CharField(max_length=500)
    rôle_du_chapitre = models.TextField(choices=ROLE_CHOICES, default='développement')
    périmètre_thématique = models.TextField()
    exclusions_thématiques = models.TextField()
    justification_indépendance_chapitre = models.TextField()
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES, default='à_rédiger')

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'chapitres'


class Section(models.Model):
    STATUT_CHOICES = [
        ('à_rédiger', 'À rédiger'),
        ('en_cours', 'En cours'),
        ('rédigé', 'Rédigé'),
        ('validé', 'Validé'),
    ]
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE)
    ordre = models.IntegerField()
    titre = models.CharField(max_length=500)
    objectif_pédagogique = models.TextField()
    périmètre_thématique = models.TextField()
    exclusions_thématiques = models.TextField()
    message_clé_à_retenir = models.TextField()
    angle_rhétorique = models.TextField(null=True, blank=True)
    texte_rédigé = models.TextField(null=True, blank=True)
    nombre_de_mots_cible = models.IntegerField(null=True, blank=True)
    nombre_de_mots_rédigés = models.IntegerField(null=True, blank=True)
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES, default='à_rédiger')

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'sections'
        unique_together = [('chapitre', 'ordre')]


class ContenuSection(models.Model):
    section = models.OneToOneField(Section, on_delete=models.CASCADE, primary_key=True)
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE)
    contenu = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'contenu_sections'


class Glossaire(models.Model):
    terme = models.CharField(max_length=255, unique=True)
    définition_utilisée_dans_ce_livre = models.TextField()
    mise_en_garde_sur_ce_terme = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'glossaire'


class Exemple(models.Model):
    titre_de_l_exemple = models.TextField()
    description_complète_de_l_exemple = models.TextField()
    chiffres_ou_données_utilisés = models.TextField(null=True, blank=True)
    source_ou_origine = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'exemples'


class Affirmation(models.Model):
    TYPE_CHOICES = [
        ('thèse', 'Thèse'),
        ('convention', 'Convention'),
        ('renvoi', 'Renvoi'),
        ('mise_en_garde', 'Mise en garde'),
    ]
    contenu_de_l_affirmation = models.TextField()
    type_affirmation = models.CharField(max_length=50, choices=TYPE_CHOICES)
    à_ne_pas_contredire = models.BooleanField(default=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'affirmations_posées'



# Tables de recherche

class IdeeRecherchee(models.Model):
    contenu_de_l_idée = models.TextField()
    placée = models.BooleanField(default=False)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'idees_recherchees'


class NotionIndispensable(models.Model):
    contenu_de_la_notion = models.TextField()
    placée = models.BooleanField(default=False)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'notions_indispensables'


class ErreurFrequente(models.Model):
    contenu_de_l_erreur = models.TextField()
    placée = models.BooleanField(default=False)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'erreurs_frequentes'


class EtapeEssentielle(models.Model):
    contenu_de_l_etapes = models.TextField()
    placée = models.BooleanField(default=False)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'etapes_essentielles'


class Risque(models.Model):
    contenu_du_risque = models.TextField()
    placée = models.BooleanField(default=False)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'risque'


class ProcessStatus(models.Model):
    progress = models.IntegerField(default=0)
    message = models.CharField(max_length=255, blank=True)
    is_done = models.BooleanField(default=False)
    redirect_url = models.CharField(max_length=255, blank=True)

    sujet_precis = models.TextField(blank=True)


    class Meta:
        db_table = 'ProcessStatus'

#Adaptation travail génération avancé
class FicheCadrage(models.Model):
    sujet                = models.TextField(null=True, blank=True)
    nb_chapitre          = models.IntegerField(null=True, blank=True)
    hors_perimetre       = models.TextField(null=True, blank=True)
    contraintes_specifiques = models.TextField(null=True, blank=True)
    cible                = models.TextField(null=True, blank=True)
    niveau               = models.TextField(null=True, blank=True)
    objectif_lecteur     = models.TextField(null=True, blank=True)
    livre_id             = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "FicheCadrage"

class Introduction(models.Model):
    contexte = models.TextField(null=True, blank=True)
    importance = models.TextField(null=True, blank=True)
    adresse_a = models.TextField(null=True, blank=True)
    organisation = models.TextField(null=True, blank=True)
    promesse = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'Introduction'

class Conclusion(models.Model):
    synthese = models.TextField(null=True, blank=True)
    logique_ensemble = models.TextField(null=True, blank=True)
    prochaines_etapes = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'Conclusion'

class FilRouge(models.Model):
    personnage = models.TextField(null=True, blank=True)
    situation_depart = models.TextField(null=True, blank=True)
    evolution = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'FilRouge'


class ChapitreDetails(models.Model):
    numero = models.IntegerField(null=True, blank=True)
    titre = models.CharField(max_length=255, null=True, blank=True)
    traite = models.TextField(null=True, blank=True)
    ne_traite_pas = models.TextField(null=True, blank=True)
    pourquoi_distinct = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'ChapitreDetails'


class SectionDetaillee(models.Model):
    chapitre = models.ForeignKey(
        ChapitreDetails,
        on_delete=models.CASCADE,
        related_name="sections",
        null=True,
        blank=True
    )

    numero = models.IntegerField(null=True, blank=True)
    titre_section = models.CharField(max_length=255, null=True, blank=True)

    objectif = models.TextField(null=True, blank=True)
    concept_cle = models.TextField(null=True, blank=True)
    exemple = models.TextField(null=True, blank=True)
    limite = models.TextField(null=True, blank=True)

    mots_cible = models.CharField(max_length=50, null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'SectionDetaillee'
        ordering = ["numero"]

class IntroductionTexte(models.Model):
    intro = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'IntroductionTexte'

class FicheSection(models.Model):
    section = models.ForeignKey(
        SectionDetaillee,
        on_delete=models.CASCADE,
        related_name="fiches",
        null=True,
        blank=True
    )

    chapitre_numero = models.IntegerField(null=True, blank=True)
    section_numero = models.IntegerField(null=True, blank=True)

    these_centrale = models.TextField(null=True, blank=True)

    arguments_cles = models.JSONField(null=True, blank=True)
    concepts_introduits = models.JSONField(null=True, blank=True)
    a_ne_pas_repeter = models.JSONField(null=True, blank=True)

    liens_chapitres = models.TextField(null=True, blank=True)
    ton_angle = models.TextField(null=True, blank=True)

    raw = models.TextField(null=True, blank=True)  # ton _raw

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "FicheSection"

class ContenuSections(models.Model):
    chapitre_numero = models.IntegerField(null=True, blank=True)
    section_numero = models.IntegerField(null=True, blank=True)

    titre = models.TextField(null=True, blank=True)
    contenu = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "ContenuSections"

class ResumeSection(models.Model):
    section = models.OneToOneField(
        SectionDetaillee,
        on_delete=models.CASCADE,
        related_name="resume",
        null=True,
        blank=True
    )

    chapitre_numero = models.IntegerField(null=True, blank=True)
    section_numero = models.IntegerField(null=True, blank=True)

    resume = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "ResumeSection"


class SectionTexte(models.Model):
    chapitre = models.IntegerField(null=True, blank=True)
    section = models.IntegerField(null=True, blank=True)
    contenu = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "SectionTexte"

class ConclusionTexte(models.Model):
    conclusion = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'ConclusionTexte'

class Variables(models.Model):
    nb_chapitre = models.IntegerField(null=True, blank=True)
    nb_mots_cible = models.IntegerField(null=True, blank=True)


    class Meta:
        db_table = 'Variables'

class Etapes(models.Model):
    sujet = models.BooleanField(default=False)
    fiche_cadrage = models.BooleanField(default=False)
    recherche = models.BooleanField(default=False)
    plan = models.BooleanField(default=False)
    structure = models.BooleanField(default=False)
    introduction = models.BooleanField(default=False)
    preface = models.BooleanField(default=False)
    contenu = models.BooleanField(default=False)
    conclusion = models.BooleanField(default=False)
    postface = models.BooleanField(default=False)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'Etapes'

class Livre(models.Model):
    livre_id = models.IntegerField(null=True, blank=True, unique=True)
    livre_titre = models.CharField(max_length=255, null=True, blank=True, unique=True)
    class Meta:
        db_table = 'Livre'

# Ajouter ces deux modèles à la fin de models.py

class FilRougeInsertion(models.Model):
    """Une insertion fil rouge par section, générée par gen_filrouge."""
    chapitre_numero = models.IntegerField(null=True, blank=True)
    section_numero = models.IntegerField(null=True, blank=True)
    contenu = models.TextField(null=True, blank=True)  # le texte narratif à insérer

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "FilRougeInsertion"
        unique_together = [("chapitre_numero", "section_numero", "livre_id")]


class SectionTexteEnrichi(models.Model):
    """Section après fusion avec le fil rouge, produite par merge_filrouge."""
    chapitre = models.IntegerField(null=True, blank=True)
    section = models.IntegerField(null=True, blank=True)
    contenu = models.TextField(null=True, blank=True)  # texte enrichi

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "SectionTexteEnrichi"
        unique_together = [("chapitre", "section", "livre_id")]


class WebSearchIdee(models.Model):
    """Une requête/idée générée par le LLM pour la recherche web (webinput)."""
    contenu = models.TextField(null=True, blank=True)

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "WebSearchIdee"


class WebSearchSummary(models.Model):
    """Résumé final de la recherche web (weboutput) — une entrée par livre."""
    sujet = models.TextField(null=True, blank=True)
    notions_indispensables = models.JSONField(null=True, blank=True)  # liste de {contenu}
    erreurs_frequentes = models.JSONField(null=True, blank=True)  # liste de {contenu}
    etapes_essentielles = models.JSONField(null=True, blank=True)  # liste de {contenu}
    risque = models.JSONField(null=True, blank=True)  # liste de {contenu}

    livre_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "WebSearchSummary"


class Preface(models.Model):
    livre_id = models.IntegerField(null=True, blank=True)
    contenu = models.TextField()
    nb_mots = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Preface"


class Postface(models.Model):
    livre_id = models.IntegerField(null=True, blank=True)
    contenu = models.TextField()
    nb_mots = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Postface"