CREATE TABLE fiche_strategique (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    sujet_précis                                TEXT NOT NULL,
    cible                                       TEXT NOT NULL,
    niveau                                      TEXT NOT NULL,
    objectif_lecteur                            TEXT NOT NULL,
    logique_ordre_des_chapitres                 TEXT NOT NULL DEFAULT 'chronologique',
    sujets_exclus_du_livre                      TEXT,
    contraintes_éditoriales                     TEXT,

    fiche_validée_par_humain                    BOOLEAN NOT NULL DEFAULT FALSE,


    CONSTRAINT niveau_valide CHECK (
        niveau IN ('débutant', 'intermédiaire', 'avancé')
    ),
    CONSTRAINT une_seule_fiche CHECK (id = 1)
);

CREATE TABLE chapitres (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    ordre                                       INTEGER NOT NULL UNIQUE,
    titre                                       TEXT NOT NULL,
    rôle_du_chapitre                            TEXT NOT NULL DEFAULT 'développement',

    périmètre_thématique                        TEXT NOT NULL,
    exclusions_thématiques                      TEXT NOT NULL,
    justification_indépendance_chapitre         TEXT NOT NULL,

    statut                                      TEXT NOT NULL DEFAULT 'à_rédiger',


    CONSTRAINT rôle_valide CHECK (
        rôle_du_chapitre IN ('introduction', 'développement', 'conclusion')
    ),
    CONSTRAINT statut_valide CHECK (
        statut IN ('à_rédiger', 'en_cours', 'rédigé', 'validé')
    )
);

CREATE TABLE sections (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    chapitre_id                                 INTEGER NOT NULL,
    ordre                                       INTEGER NOT NULL,
    titre                                       TEXT NOT NULL,

    objectif_pédagogique                        TEXT NOT NULL,
    périmètre_thématique                        TEXT NOT NULL,
    exclusions_thématiques                      TEXT NOT NULL,
    message_clé_à_retenir                       TEXT NOT NULL,
    angle_rhétorique                            TEXT,

    texte_rédigé                                TEXT,
    nombre_de_mots_cible                        INTEGER,
    nombre_de_mots_rédigés                      INTEGER,

    statut                                      TEXT NOT NULL DEFAULT 'à_rédiger',


    FOREIGN KEY (chapitre_id) REFERENCES chapitres(id) ON DELETE CASCADE,

    CONSTRAINT ordre_unique_par_chapitre UNIQUE (chapitre_id, ordre),
    CONSTRAINT statut_valide CHECK (
        statut IN ('à_rédiger', 'en_cours', 'rédigé', 'validé')
    )
);


CREATE TABLE contenu_sections(
    section_id INTEGER PRIMARY KEY,
    chapitre_id INTEGER,
    contenu TEXT,
    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
    FOREIGN KEY (chapitre_id) REFERENCES chapitres(id) ON DELETE CASCADE
);

CREATE TABLE glossaire (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    terme                                       TEXT NOT NULL UNIQUE,
    définition_utilisée_dans_ce_livre           TEXT NOT NULL,
    mise_en_garde_sur_ce_terme                  TEXT

);

CREATE TABLE exemples (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    titre_de_l_exemple                          TEXT NOT NULL,
    description_complète_de_l_exemple           TEXT NOT NULL,
    chiffres_ou_données_utilisés                TEXT,
    source_ou_origine                           TEXT

);

CREATE TABLE affirmations_posées (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    contenu_de_l_affirmation                    TEXT NOT NULL,
    type_affirmation                           TEXT NOT NULL,
    à_ne_pas_contredire                         BOOLEAN NOT NULL DEFAULT TRUE,


    CONSTRAINT type_valide CHECK (
        type_affirmation IN ('thèse', 'convention', 'renvoi', 'mise_en_garde')
    )
);

CREATE TABLE checkpoints (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    étape                                       TEXT NOT NULL,
    validé_par_humain                           BOOLEAN NOT NULL DEFAULT FALSE,
    commentaire_du_validateur                   TEXT,

);

CREATE TABLE sections_glossaire (
    section_id                                  INTEGER NOT NULL,
    terme_id                                    INTEGER NOT NULL,

    le_terme_est_défini_ici                     BOOLEAN NOT NULL DEFAULT TRUE,
    comment_le_terme_est_mobilisé               TEXT,

    PRIMARY KEY (section_id, terme_id),

    FOREIGN KEY (section_id)    REFERENCES sections(id)     ON DELETE CASCADE,
    FOREIGN KEY (terme_id)      REFERENCES glossaire(id)    ON DELETE CASCADE
);

CREATE TABLE sections_exemples (
    section_id                                  INTEGER NOT NULL,
    exemple_id                                  INTEGER NOT NULL,

    l_exemple_est_introduit_ici                 BOOLEAN NOT NULL DEFAULT TRUE,
    comment_l_exemple_est_mobilisé              TEXT,

    PRIMARY KEY (section_id, exemple_id),

    FOREIGN KEY (section_id)    REFERENCES sections(id)     ON DELETE CASCADE,
    FOREIGN KEY (exemple_id)    REFERENCES exemples(id)     ON DELETE CASCADE
);

CREATE TABLE sections_affirmations (
    section_id                                  INTEGER NOT NULL,
    affirmation_id                              INTEGER NOT NULL,

    l_affirmation_est_introduite_ici            BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (section_id, affirmation_id),

    FOREIGN KEY (section_id)        REFERENCES sections(id)                 ON DELETE CASCADE,
    FOREIGN KEY (affirmation_id)    REFERENCES affirmations_posées(id)      ON DELETE CASCADE
);



--Recherches--

CREATE TABLE idees_recherchees (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    contenu_de_l_idée                           TEXT NOT NULL,
    placée                                      BOOLEAN NOT NULL DEFAULT FALSE,
    section_id                                  INTEGER DEFAULT NULL

);

CREATE TABLE notions_indispensables (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nom_de_la_notion                            TEXT NOT NULL,
    contenu_de_la_notion                        TEXT NOT NULL,
    placée                                      BOOLEAN NOT NULL DEFAULT FALSE,
    section_id                                  INTEGER DEFAULT NULL
);

CREATE TABLE erreurs_frequentes (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    contenu_de_l_erreur                         TEXT NOT NULL,
    placée                                      BOOLEAN NOT NULL DEFAULT FALSE,
    section_id                                  INTEGER DEFAULT NULL
);

CREATE TABLE etapes_essentielles (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    contenu_de_l_etapes                         TEXT NOT NULL,
    placée                                      BOOLEAN NOT NULL DEFAULT FALSE,
    section_id                                  INTEGER DEFAULT NULL
);

CREATE TABLE risque (
    id                                          INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    contenu_du_risque                           TEXT NOT NULL,
    placée                                      BOOLEAN NOT NULL DEFAULT FALSE,
    section_id                                  INTEGER DEFAULT NULL
);



