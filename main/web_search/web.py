import os

import requests
import json
from datetime import datetime


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
    max_results = 3 # Nombre maximum de résultats à prendre en compte
    for result in results["organic_results"][:max_results]:
        clean_results.append({
            "title": result.get("title"),
            "url": result.get("link"),
            "snippet": result.get("snippet")
        })

    filepath = os.path.join("output", f"api_result-{timestamp}.json")
    with open(filepath, "a", encoding="utf-8") as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)
    return json.dumps(clean_results, ensure_ascii=False, indent=2)

def web_search_wrapper():
    sujet_path = os.path.join("output", "ws_search.json")
    with open(sujet_path, "r", encoding="utf-8") as f:
        sujets = json.load(f)

    all_results = []
    for sujet in sujets["idees"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = web_search(sujet["contenu_de_l_idée"], timestamp)
        # results est une chaîne JSON renvoyée par le LLM, on la parse
        try:
            parsed = json.loads(results)
        except json.JSONDecodeError:
            parsed = results
        all_results.append(parsed)

    filepath = os.path.join("output", "ws_pertinent.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    web_search_wrapper()