import os
import json
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]


def fetch_page_content(url: str, timeout: int = 15) -> str | None:
    """Récupère le contenu textuel principal d'une page web."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "lxml")

        # Supprimer les balises inutiles
        for tag in soup.find_all(TAGS_TO_REMOVE):
            tag.decompose()

        # Chercher le contenu principal (article ou main), sinon body
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if main is None:
            return None

        text = main.get_text(separator="\n", strip=True)

        # Nettoyer les lignes vides multiples
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    except Exception as e:
        print(f"  ✗ Erreur pour {url} : {e}")
        return None


def fetch_all_sources(input_path: str, output_path: str, search_path: str = None):
    """Lit ws_pertinent.json, visite chaque URL et sauvegarde le contenu."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Charger les sujets depuis ws_search.json si disponible
    sujets = []
    if search_path and os.path.exists(search_path):
        with open(search_path, "r", encoding="utf-8") as f:
            search_data = json.load(f)
        sujets = [idee.get("contenu_de_l_idée", "") for idee in search_data.get("idees", [])]

    results = []

    for i, bloc in enumerate(data):
        # Gérer les deux formats : liste de listes ou liste de dicts
        if isinstance(bloc, list):
            sources = bloc
            sujet = sujets[i] if i < len(sujets) else f"Recherche {i + 1}"
        else:
            sujet = bloc.get("sujet", f"Recherche {i + 1}")
            sources = bloc.get("sources", [])
        print(f"\n[Bloc {i + 1}] {sujet[:80]}...")

        fetched_sources = []
        for source in sources:
            url = source.get("url", "")
            title = source.get("title", source.get("titre", ""))
            print(f"  → {title}")
            print(f"    {url}")

            content = fetch_page_content(url)

            fetched_sources.append({
                "title": title,
                "url": url,
                "content": content,
                "success": content is not None,
                "length": len(content) if content else 0,
            })

            status = f"✓ {len(content)} caractères" if content else "✗ Échec"
            print(f"    {status}")

        results.append({
            "sujet": sujet,
            "sources": fetched_sources,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Stats
    total = sum(len(r["sources"]) for r in results)
    ok = sum(1 for r in results for s in r["sources"] if s["success"])
    print(f"\nTerminé : {ok}/{total} pages récupérées")
    print(f"Résultat sauvegardé dans {output_path}")


def webfetch_wrapper():
    input_path = os.path.join("output", "ws_pertinent.json")
    output_path = os.path.join("output", "ws_content.json")
    search_path = os.path.join("output", "ws_search.json")
    fetch_all_sources(input_path, output_path, search_path)

if __name__ == "__main__":
    webfetch_wrapper()
