import json
import os
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from ...models import WebSearchIdee, WebSearchSummary
from ...settings import BASE_DIR
from ..fiche_cadrage import recup_fiche_cadrage
from ..llm_fallback import chat_with_major_error_fallback
from ..parser import read_text_file

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT_DIR = Path(BASE_DIR).parents[0]
INPUT_DIR = Path(BASE_DIR) / "Stage/input/web_search/"

load_dotenv(ROOT_DIR / "param.env")
SERP_API_KEY = os.getenv("VALUESERP_API_KEY") or os.getenv("SERP_API_KEY")

MODEL_COURT = os.getenv("ED_BELLUS_OLLAMA_MODEL_COURT")
MODEL_LONG = os.getenv("ED_BELLUS_OLLAMA_MODEL_LONG")
LLM_MAX_RETRIES = 4
LLM_BASE_DELAY_SECONDS = 2

MAX_SOURCE_CONTENT_CHARS = 30000
MAX_PARTIAL_SUMMARY_CHARS = 2500
MAX_MERGE_INPUT_CHARS = 50000
MAX_SERP_RESULTS = 5
TRUNCATION_MARKER = "\n\n[... contenu tronque ...]"

QUERY_KEYS = (
    "contenu_de_l_idée",
    "contenu_de_l'idée",
    "contenu_de_l_idee",
    "query",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def _chat(message_content: str, context_label: str, model: str) -> str:
    return chat_with_major_error_fallback(
        ollama_model=model,
        message_content=message_content,
        context_label=context_label,
        ollama_max_retries=LLM_MAX_RETRIES,
        ollama_retry_delay_seconds=LLM_BASE_DELAY_SECONDS,
    )


# ---------------------------------------------------------------------------
# Helpers texte
# ---------------------------------------------------------------------------

def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    marker_size = len(TRUNCATION_MARKER)
    if max_chars <= marker_size + 20:
        return text[:max_chars], True
    available = max_chars - marker_size
    head_size = int(available * 0.8)
    tail_size = available - head_size
    return f"{text[:head_size]}{TRUNCATION_MARKER}{text[-tail_size:]}", True


def _extract_query(idee: dict, index: int) -> str:
    if not isinstance(idee, dict):
        raise ValueError(f"idees[{index}] doit etre un objet JSON.")
    for key in QUERY_KEYS:
        value = idee.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise KeyError(f"Aucune cle de requete valide pour idees[{index}].")


def _load_queries(payload: dict) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError("Le contenu WebSearchQuery doit etre un objet JSON.")
    idees = payload.get("idees")
    if not isinstance(idees, list):
        raise ValueError("Le payload WebSearchQuery doit contenir une liste 'idees'.")
    return [_extract_query(idee, idx) for idx, idee in enumerate(idees)]


# ---------------------------------------------------------------------------
# Étape 1 — webinput : génère les requêtes
# ---------------------------------------------------------------------------

def webinput(livre_id: int) -> dict:
    """Génère les requêtes de recherche via le LLM et les sauvegarde en BDD."""
    fiche_raw = recup_fiche_cadrage(livre_id)

    prompt_path = INPUT_DIR / "ws_search.txt"
    prompt = read_text_file(prompt_path, "prompt web search", require_non_empty=False)

    raw_response = _chat(
        message_content=f"{prompt}\n\nSUJET : {fiche_raw}",
        context_label="webinput",
        model=MODEL_COURT,
    )

    try:
        response_obj = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        preview = raw_response[:300].replace("\n", " ")
        raise ValueError(f"La reponse webinput doit etre un JSON valide. Extrait: {preview!r}") from exc

    if not isinstance(response_obj, dict):
        raise ValueError("Le JSON webinput doit etre un objet.")

    ajout_web_search_query(response_obj, livre_id)
    return response_obj


# ---------------------------------------------------------------------------
# Étape 2 — websearch : appels API SERP
# ---------------------------------------------------------------------------

def _web_search_single(query: str) -> list[dict]:
    """Appelle l'API SERP pour une requête et retourne les résultats nettoyés."""
    if not SERP_API_KEY:
        raise ValueError("VALUESERP_API_KEY introuvable dans les variables d'environnement.")

    params = {
        "api_key": SERP_API_KEY,
        "q": query,
        "location": "France",
        "location_auto": "false",
        "gl": "fr",
        "hl": "fr",
        "google_domain": "google.fr",
    }

    try:
        response = requests.get("https://api.valueserp.com/search", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        print(f"Echec HTTP pour la requete '{query}': {exc}")
        return []
    except ValueError:
        print(f"Reponse API invalide pour la requete: {query}")
        return []

    organic = payload.get("organic_results", [])
    if not isinstance(organic, list):
        print(f"Aucun resultat organique pour '{query}'.")
        return []

    return [
        {
            "title": r.get("title"),
            "url": r.get("link"),
            "snippet": r.get("snippet"),
        }
        for r in organic[:MAX_SERP_RESULTS]
    ]


def websearch(queries_payload: dict) -> list[dict]:
    """Lance les appels SERP pour toutes les requêtes et retourne les résultats."""
    queries = _load_queries(queries_payload)
    all_results = []
    for query in queries:
        print(f"  Recherche: {query[:80]}...")
        results = _web_search_single(query)
        all_results.append({"sujet": query, "sources": results})
    return all_results


# ---------------------------------------------------------------------------
# Étape 3 — webfetch : scraping des pages
# ---------------------------------------------------------------------------

def _fetch_page_content(url: str, timeout: int = 15) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup.find_all(TAGS_TO_REMOVE):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if main is None:
            return None
        lines = [line.strip() for line in main.get_text(separator="\n").splitlines() if line.strip()]
        return "\n".join(lines)
    except requests.RequestException as exc:
        print(f"  Erreur pour {url}: {exc}")
        return None


def webfetch(search_results: list[dict]) -> list[dict]:
    """Scrappe le contenu de chaque URL et retourne les sources enrichies."""
    results = []
    for bloc in search_results:
        if not isinstance(bloc, dict):
            continue
        sujet = bloc.get("sujet", "")
        sources = bloc.get("sources", [])
        fetched_sources = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            url = source.get("url", "")
            title = source.get("title", "")
            print(f"  Fetch: {title[:60]}...")
            content = _fetch_page_content(url)
            fetched_sources.append({
                "title": title,
                "url": url,
                "content": content,
                "success": content is not None,
                "length": len(content) if content else 0,
            })
        results.append({"sujet": sujet, "sources": fetched_sources})

    total = sum(len(r["sources"]) for r in results)
    ok = sum(1 for r in results for s in r["sources"] if s["success"])
    print(f"Fetch termine: {ok}/{total} pages recuperees.")
    return results


# ---------------------------------------------------------------------------
# Étape 4 — weboutput : résumé final via LLM
# ---------------------------------------------------------------------------

def _load_sources_from_content(content_data: list[dict]) -> list[dict]:
    all_sources = []
    for bloc in content_data:
        if not isinstance(bloc, dict):
            continue
        sujet = bloc.get("sujet", "")
        for source in bloc.get("sources", []):
            if isinstance(source, dict) and source.get("success") and source.get("content"):
                all_sources.append({
                    "sujet": sujet,
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "content": source["content"],
                })
    return all_sources


def _local_fallback_summary(sujet: str, source: dict, error_message: str) -> str:
    content = source.get("content", "")
    excerpt, _ = _truncate_text(content, 1200)
    return json.dumps({
        "sujet": sujet,
        "source": {"title": source.get("title", ""), "url": source.get("url", "")},
        "resume": excerpt,
        "warning": f"fallback_local_active ({error_message})",
    }, ensure_ascii=False)


def _summarize_single_source(prompt: str, sujet: str, source: dict) -> str:
    raw_content = source.get("content", "")
    if not isinstance(raw_content, str) or not raw_content.strip():
        return _local_fallback_summary(sujet=sujet, source=source, error_message="source_content_empty")

    content, was_truncated = _truncate_text(raw_content, MAX_SOURCE_CONTENT_CHARS)
    if was_truncated:
        print(f"   Contenu tronque ({len(raw_content)} -> {len(content)} chars)")

    try:
        return _chat(
            message_content=f"{prompt}\n\nSUJET : {sujet}\n\nRESULTATS DE LA RECHERCHE : "
                            f"Titre : {source['title']}\nURL : {source['url']}\nContenu :\n{content}",
            context_label=f"resume_source:{source.get('url', 'unknown')}",
            model=MODEL_LONG,
        )
    except Exception as exc:
        print(f"[WARN] Resume source en fallback local: {exc}")
        return _local_fallback_summary(sujet=sujet, source=source, error_message=str(exc))


def _merge_summaries(prompt: str, sujet: str, partial_summaries: list[str]) -> str:
    clipped = []
    for s in partial_summaries:
        c, _ = _truncate_text(s, MAX_PARTIAL_SUMMARY_CHARS)
        clipped.append(c)

    all_partials, _ = _truncate_text("\n---\n".join(clipped), MAX_MERGE_INPUT_CHARS)

    try:
        return _chat(
            message_content=(
                f"{prompt}\n\nSUJET : {sujet}\n\n"
                "Fusionne ces résumés partiels en UN SEUL résumé final cohérent, sans doublons, "
                "en gardant le même format JSON demandé.\n\n"
                f"RÉSUMÉS PARTIELS :\n{all_partials}"
            ),
            context_label="merge_summaries",
            model=MODEL_LONG,
        )
    except Exception as exc:
        print(f"[WARN] Fusion LLM indisponible, fallback concatene: {exc}")
        return json.dumps({
            "sujet": sujet,
            "resumes_partiels": clipped,
            "warning": f"merge_fallback_active ({exc})",
        }, ensure_ascii=False)


def weboutput(livre_id: int, content_data: list[dict]) -> dict:
    """Résume toutes les sources et sauvegarde le résultat final en BDD."""
    prompt_path = INPUT_DIR / "ws_summary.txt"
    prompt = read_text_file(prompt_path, "prompt resume web", require_non_empty=False)

    fiche_raw = recup_fiche_cadrage(livre_id)
    sources = _load_sources_from_content(content_data)

    if not sources:
        result = {"sources_web": [], "warning": "aucune_source_exploitable"}
        ajout_web_search_summary(result, livre_id)
        return result

    print(f"{len(sources)} sources a traiter.")
    partial_summaries = []
    for idx, source in enumerate(sources):
        print(f"[{idx + 1}/{len(sources)}] {source['title'][:60]}...")
        summary = _summarize_single_source(prompt, fiche_raw, source)
        partial_summaries.append(summary)

    raw_final = partial_summaries[0] if len(partial_summaries) == 1 else _merge_summaries(prompt, fiche_raw, partial_summaries)

    try:
        result = json.loads(raw_final)
    except json.JSONDecodeError:
        print("[WARN] Reponse LLM non JSON valide, sauvegarde brute.")
        result = {"raw": raw_final}

    ajout_web_search_summary(result, livre_id)
    return result


# ---------------------------------------------------------------------------
# Pipeline complet
# ---------------------------------------------------------------------------

def web_search_pipeline(livre_id: int) -> dict:
    """Enchaîne les 4 étapes : webinput → websearch → webfetch → weboutput."""
    print("Etape 1/4 — Generation des requetes...")
    queries_payload = webinput(livre_id)

    print("Etape 2/4 — Recherche web (API SERP)...")
    search_results = websearch(queries_payload)

    print("Etape 3/4 — Recuperation des contenus...")
    content_data = webfetch(search_results)

    print("Etape 4/4 — Synthese finale...")
    return weboutput(livre_id, content_data)


# ---------------------------------------------------------------------------
# BDD helpers
# ---------------------------------------------------------------------------

def ajout_web_search_query(data: dict, livre_id: int):
    """Sauvegarde les idées de recherche en BDD (une ligne par idée)."""
    WebSearchIdee.objects.filter(livre_id=livre_id).delete()
    for idee in data.get("idees", []):
        if not isinstance(idee, dict):
            continue
        # Gère les variantes de clé
        contenu = None
        for key in QUERY_KEYS:
            contenu = idee.get(key)
            if contenu:
                break
        if contenu:
            WebSearchIdee.objects.create(contenu=contenu, livre_id=livre_id)


def recup_web_search_query(livre_id: int) -> dict:
    """Restitue les idées sous le format attendu par _load_queries."""
    idees = WebSearchIdee.objects.filter(livre_id=livre_id).values_list("contenu", flat=True)
    return {"idees": [{"contenu_de_l_idee": c} for c in idees]}


def ajout_web_search_summary(data: dict, livre_id: int):
    """Sauvegarde le résumé final en BDD avec champs dédiés."""
    WebSearchSummary.objects.filter(livre_id=livre_id).delete()
    WebSearchSummary.objects.create(
        sujet=data.get("sujet"),
        notions_indispensables=data.get("notions_indispensables"),
        erreurs_frequentes=data.get("erreurs_frequentes"),
        etapes_essentielles=data.get("etapes_essentielles"),
        risque=data.get("risque"),
        livre_id=livre_id,
    )


def recup_web_search(livre_id: int) -> dict | None:
    """Retourne le résumé final sous forme de dict."""
    obj = WebSearchSummary.objects.filter(livre_id=livre_id).last()
    if not obj:
        return None
    return {
        "sujet": obj.sujet,
        "notions_indispensables": obj.notions_indispensables,
        "erreurs_frequentes": obj.erreurs_frequentes,
        "etapes_essentielles": obj.etapes_essentielles,
        "risque": obj.risque,
    }


def reset_web_search(livre_id: int):
    WebSearchIdee.objects.filter(livre_id=livre_id).delete()
    WebSearchSummary.objects.filter(livre_id=livre_id).delete()
