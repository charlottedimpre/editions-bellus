

def clean_json(data, schema):
    """
    Nettoie un dictionnaire JSON ou une liste de dictionnaires selon un schéma.

    data : dict | list -> JSON à nettoyer
    schema : dict -> définition des clés autorisées et règles

    Retourne un nouveau JSON avec uniquement les clés autorisées et valeurs valides.
    """

    if isinstance(data, list):
        return [clean_json(item, schema) for item in data]

    if not isinstance(data, dict):
        return data  # valeurs simples, on ne fait rien

    cleaned = {}

    for key, value in data.items():
        if key not in schema:
            continue  # clé non autorisée, on ignore

        rules = schema[key]

        # Récursion pour sous-dictionnaires
        if isinstance(value, dict) and "schema" in rules:
            cleaned[key] = clean_json(value, rules["schema"])
        elif isinstance(value, list) and "schema" in rules:
            cleaned[key] = [clean_json(v, rules["schema"]) for v in value]
        else:
            cleaned[key] = value

        # Vérification valeurs autorisées
        if "allowed" in rules and cleaned[key] not in rules["allowed"]:
            cleaned[key] = rules.get("default")

        # Conversion de type
        if "type" in rules:
            try:
                cleaned[key] = rules["type"](cleaned[key])
            except (ValueError, TypeError):
                cleaned[key] = rules.get("default")

        # Minimum et maximum (pour int ou float)
        if isinstance(cleaned[key], (int, float)):
            if "min" in rules and cleaned[key] < rules["min"]:
                cleaned[key] = rules["min"]
            if "max" in rules and cleaned[key] > rules["max"]:
                cleaned[key] = rules["max"]

    # Ajouter les clés manquantes avec valeur par défaut
    for key, rules in schema.items():
        if key not in cleaned:
            cleaned[key] = rules.get("default")

    return cleaned

def filtrer_champs_valides(table, champs):
    CHAMPS_VALIDES = {
        "sections": {
            "chapitre_id",
            "ordre",
            "titre",
            "objectif_pédagogique",
            "périmètre_thématique",
            "exclusions_thématiques",
            "message_clé_à_retenir",
            "angle_rhétorique",
            "nombre_de_mots_cible"
        },
        "chapitres": {
            "ordre",
            "titre",
            "rôle_du_chapitre",
            "périmètre_thématique",
            "exclusions_thématiques",
            "justification_indépendance_chapitre"
        }
    }

    allowed = CHAMPS_VALIDES.get(table, set())

    return {
        k: v for k, v in champs.items()
        if k in allowed
    }

def clean_champs(table, champs):
    if table == "sections":
        allowed = SECTION_FIELDS
    elif table == "chapitres":
        allowed = CHAPITRE_FIELDS
    else:
        return {}

    cleaned = {}

    for key, value in champs.items():
        if key not in allowed:
            continue

        expected_type = allowed[key]

        try:
            cleaned[key] = expected_type(value)
        except:
            continue

    return cleaned


PLAN_SCHEMA = {
    "chapitres": {
        "schema": {
            "ordre": {"type": int, "default": 1},
            "titre": {"type": str, "default": ""},
            "rôle_du_chapitre": {
                "type": str,
                "allowed": ["introduction", "développement", "conclusion"],
                "default": "développement"
            },
            "périmètre_thématique": {"type": str, "default": ""},
            "exclusions_thématiques": {"type": str, "default": ""},
            "justification_indépendance_chapitre": {"type": str, "default": ""},
            "sections": {
                "schema": {
                    "ordre": {"type": int, "default": 1},
                    "titre": {"type": str, "default": ""},
                    "objectif_pédagogique": {"type": str, "default": ""},
                    "périmètre_thématique": {"type": str, "default": ""},
                    "exclusions_thématiques": {"type": str, "default": ""},
                    "message_clé_à_retenir": {"type": str, "default": ""},
                    "angle_rhétorique": {"type": str, "default": ""},
                    "nombre_de_mots_cible": {
                        "type": int,
                        "min": 600,
                        "max": 4000,
                        "default": 800
                    }
                }
            }
        }
    }
}

PLAN_VERIF_SCHEMA = {
    "probleme": {"type": str, "default": ""},

    "reparation": {
        "schema": {
            "action": {
                "type": str,
                "allowed": ["ajouter", "supprimer", "modifier", "déplacer", "fusionner"],
                "default": "modifier"
            },

            "table": {
                "type": str,
                "allowed": ["chapitres", "sections"],
                "default": "sections"
            },

            "id": {"type": int, "default": None},

            # 🔥 clé critique
            "champs_a_modifier": {
                "schema": {
                    # ⚠️ on laisse VIDE ici → on filtrera dynamiquement
                }
            },

            "detail": {"type": str, "default": ""}
        }
    }
}

SECTION_FIELDS = {
    "chapitre_id": int,
    "ordre": int,
    "titre": str,
    "objectif_pédagogique": str,
    "périmètre_thématique": str,
    "exclusions_thématiques": str,
    "message_clé_à_retenir": str,
    "angle_rhétorique": str,
    "nombre_de_mots_cible": int,
}

CHAPITRE_FIELDS = {
    "ordre": int,
    "titre": str,
    "rôle_du_chapitre": str,
    "périmètre_thématique": str,
    "exclusions_thématiques": str,
    "justification_indépendance_chapitre": str,
}

INFOS_SCHEMA = {
    "actions": {
        "type": list,
        "default": [],
        "schema": {
            "action": {
                "type": str,
                "allowed": ["ajouter", "modifier"],
                "default": "ajouter"
            },
            "table": {
                "type": str,
                "allowed": ["glossaire", "exemples", "affirmations_posées"],
                "default": "glossaire"
            },
            "id": {
                "type": int,
                "default": None
            },
            "données": {
                "type": dict,
                "default": {},
                "schema": {

                    # 🔹 GLOSSAIRE
                    "terme": {"type": str, "default": ""},
                    "définition_utilisée_dans_ce_livre": {"type": str, "default": ""},
                    "mise_en_garde_sur_ce_terme": {"type": str, "default": None},

                    # 🔹 EXEMPLES
                    "titre_de_l_exemple": {"type": str, "default": ""},
                    "description_complète_de_l_exemple": {"type": str, "default": ""},
                    "chiffres_ou_données_utilisés": {"type": str, "default": None},
                    "source_ou_origine": {"type": str, "default": None},

                    # 🔹 AFFIRMATIONS
                    "contenu_de_l_affirmation": {"type": str, "default": ""},
                    "type_affirmation": {
                        "type": str,
                        "allowed": ["thèse", "convention", "renvoi", "mise_en_garde"],
                        "default": "thèse"
                    },
                    "à_ne_pas_contredire": {
                        "type": bool,
                        "default": True
                    }
                }
            }
        }
    }
}