from pathlib import Path
import os

import requests
import json
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT_DIR / ".envt")
SERP_API_KEY = os.getenv("VALUESERP_API_KEY") or os.getenv("SERP_API_KEY")
SERP_API_KEY = "0D48DFE77B86417A95187BE6E08D2FBD"
if not SERP_API_KEY:
    raise ValueError("VALUESERP_API_KEY introuvable dans le fichier .env")

QUERY_KEYS = (
    "contenu_de_l_idée",
    "contenu_de_l'idée",
    "contenu_de_l_idee",
    "query",
)


def _extract_query(idee: dict, index: int) -> str:
    for key in QUERY_KEYS:
        value = idee.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise KeyError(
        f"Aucune cle de requete valide pour idees[{index}] "
        f"(cles attendues: {', '.join(QUERY_KEYS)})."
    )


def _load_queries(payload: dict) -> list[str]:
    idees = payload.get("idees")
    if not isinstance(idees, list):
        raise ValueError("Le fichier ws_search.json doit contenir une liste 'idees'.")
    return [_extract_query(idee, idx) for idx, idee in enumerate(idees)]


def _safe_api_json(api_result: requests.Response, query: str) -> dict:
    try:
        payload = api_result.json()
    except ValueError:
        print(f"Reponse API invalide pour la requete: {query}")
        return {}

    if not isinstance(payload, dict):
        print(f"Format de reponse inattendu pour la requete: {query}")
        return {}
    return payload


def _extract_organic_results(payload: dict, query: str) -> list[dict]:
    organic_results = payload.get("organic_results")
    if isinstance(organic_results, list):
        return organic_results

    error_info = payload.get("error")
    if error_info:
        print(f"Aucun resultat organique pour '{query}' (erreur API: {error_info})")
    else:
        print(f"Aucun resultat organique pour '{query}' (cle 'organic_results' absente).")
    return []


def web_search(query, timestamp):
    params = {
        'api_key': SERP_API_KEY,
        'q': f'{query}',
        'location': 'France',
        'location_auto': 'false',
        'gl': 'fr',
        'hl': 'fr',
        'google_domain': 'google.fr'
    }

    try:
        api_result = requests.get('https://api.valueserp.com/search', params=params, timeout=20)
    except requests.RequestException as exc:
        print(f"Echec HTTP pour la requete '{query}': {exc}")
        return json.dumps([], ensure_ascii=False, indent=2)

    results = _safe_api_json(api_result, query)
    organic_results = _extract_organic_results(results, query)

    clean_results = []
    max_results = 5  # Nombre maximum de résultats à prendre en compte
    for result in organic_results[:max_results]:
        clean_results.append({
            "title": result.get("title"),
            "url": result.get("link"),
            "snippet": result.get("snippet")
        })

    filepath = OUTPUT_DIR / f"api_result-{timestamp}.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return json.dumps(clean_results, ensure_ascii=False, indent=2)


def web_search_wrapper():
    sujet_path = OUTPUT_DIR / "ws_search.json"
    with sujet_path.open("r", encoding="utf-8") as f:
        sujets = json.load(f)

    queries = _load_queries(sujets)

    all_results = []
    for query in queries:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = web_search(query, timestamp)
        # results est une chaîne JSON renvoyée par le LLM, on la parse
        try:
            parsed = json.loads(results)
        except json.JSONDecodeError:
            parsed = results
        all_results.append(parsed)

    filepath = OUTPUT_DIR / "ws_pertinent.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    web_search_wrapper()