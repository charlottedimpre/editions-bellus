from pathlib import Path
import requests
from bs4 import BeautifulSoup
from parser import read_json_file, write_json_file as _write_json

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

QUERY_KEYS = (
    "contenu_de_l_idée",
    "contenu_de_l'idée",
    "contenu_de_l_idee",
    "query",
)


def _extract_query(idee: dict) -> str:
    for key in QUERY_KEYS:
        value = idee.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]

def _read_json(path: Path, label: str):
    return read_json_file(path, label, require_non_empty=False)


def fetch_page_content(url: str, timeout: int = 15) -> str | None:
    """Récupère le contenu textuel principal d'une page web."""
    if not isinstance(url, str) or not url.strip():
        return None

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

        text = main.get_text(separator="\n")

        # Nettoyer les lignes vides multiples
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    except requests.RequestException as e:
        print(f"  ✗ Erreur pour {url} : {e}")
        return None


def fetch_all_sources(input_path: Path, output_path: Path, search_path: Path | None = None):
    """Lit ws_pertinent.json, visite chaque URL et sauvegarde le contenu."""
    data = _read_json(input_path, "sources web pertinentes")
    if not isinstance(data, list):
        raise ValueError("ws_pertinent.json doit contenir une liste.")

    # Charger les sujets depuis ws_search.json si disponible
    sujets = []
    if search_path and search_path.exists():
        search_data = _read_json(search_path, "requetes web")
        if isinstance(search_data, dict):
            raw_idees = search_data.get("idees", [])
            if isinstance(raw_idees, list):
                sujets = [_extract_query(idee) for idee in raw_idees if isinstance(idee, dict)]

    results = []

    for i, bloc in enumerate(data):
        # Gérer les deux formats : liste de listes ou liste de dicts
        if isinstance(bloc, list):
            sources = bloc
            sujet = sujets[i] if i < len(sujets) else f"Recherche {i + 1}"
        elif isinstance(bloc, dict):
            sujet = bloc.get("sujet", f"Recherche {i + 1}")
            sources = bloc.get("sources", [])
            if not isinstance(sources, list):
                sources = []
        else:
            sujet = f"Recherche {i + 1}"
            sources = []

        print(f"\n[Bloc {i + 1}] {sujet[:80]}...")

        fetched_sources = []
        for source in sources:
            if not isinstance(source, dict):
                continue

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
            "sujet": str(sujet),
            "sources": fetched_sources,
        })

    _write_json(output_path, results, "contenus web recuperes")

    # Stats
    total = sum(len(r["sources"]) for r in results)
    ok = sum(1 for r in results for s in r["sources"] if s["success"])
    print(f"\nTerminé : {ok}/{total} pages récupérées")
    print(f"Résultat sauvegardé dans {output_path}")

    return results


def webfetch_wrapper():
    input_path = OUTPUT_DIR / "ws_pertinent.json"
    output_path = OUTPUT_DIR / "ws_content.json"
    search_path = OUTPUT_DIR / "ws_search.json"
    fetch_all_sources(input_path, output_path, search_path)


if __name__ == "__main__":
    webfetch_wrapper()
