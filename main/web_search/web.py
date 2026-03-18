from pathlib import Path

import requests
import json
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


def web_search(query, timestamp):
    params = {
        'api_key': '585CC66616DB4440AD3D8B7426E8387B',
        'q': f'{query}',
        'location': 'France',
        'location_auto': 'false',
        'gl': 'fr',
        'hl': 'fr',
        'google_domain': 'google.fr'
    }

    api_result = requests.get('https://api.valueserp.com/search', params)

    results = api_result.json()

    clean_results = []
    max_results = 5  # Nombre maximum de résultats à prendre en compte
    for result in results["organic_results"][:max_results]:
        clean_results.append({
            "title": result.get("title"),
            "url": result.get("link"),
            "snippet": result.get("snippet")
        })

    filepath = OUTPUT_DIR / f"api_result-{timestamp}.json"
    with filepath.open("a", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)
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