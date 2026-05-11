import json
import re


def clean_text(text: str) -> str:
    if not text:
        return ""

    # supprimer markdown
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)

    # trim
    text = text.strip()

    return text


def extract_json_block(text: str) -> str:
    """
    Extrait le premier bloc JSON {...}
    """
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("Aucun JSON trouvé")

    return text[start:end+1]


def repair_json(text: str) -> str:
    """
    Réparations basiques
    """
    # guillemets simples → doubles
    text = text.replace("'", '"')

    # supprimer virgule finale
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    return text


def safe_json(text: str) -> dict:
    """
    Parse JSON avec fallback robuste
    """
    cleaned = clean_text(text)

    try:
        extracted = extract_json_block(cleaned)
    except Exception:
        print("❌ Aucun JSON détecté")
        return {}

    try:
        return json.loads(extracted)

    except Exception:
        print("⚠️ JSON cassé → tentative réparation")

        try:
            repaired = repair_json(extracted)
            return json.loads(repaired)

        except Exception:
            print("❌ JSON irréparable")
            print(extracted[:500])
            return {}