import json
import os

from ollama import ChatResponse, chat

MODEL = 'kimi-k2.5:cloud'


def load_prompt():
    filepath = os.path.join("input", "ws_summary.txt")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def load_sujet():
    sujet_path = os.path.join("..", "fiche_cadrage", "output", "fiche_cadrage.json")
    with open(sujet_path, "r", encoding="utf-8") as f:
        return f.read()


def load_sources():
    """Charge ws_content.json et retourne une liste plate de toutes les sources."""
    webresponse_path = os.path.join("output", "ws_content.json")
    with open(webresponse_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_sources = []
    for bloc in data:
        sujet = bloc.get("sujet", "")
        for source in bloc.get("sources", []):
            if source.get("success") and source.get("content"):
                all_sources.append({
                    "sujet": sujet,
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "content": source["content"]
                })
    return all_sources


def summarize_single_source(prompt: str, sujet: str, source: dict) -> str:
    """Résume une seule source via le LLM."""
    source_text = (
        f"Titre : {source['title']}\n"
        f"URL : {source['url']}\n"
        f"Contenu :\n{source['content']}"
    )

    print(f"   Résumé de : {source['title'][:80]}...")

    response: ChatResponse = chat(model=MODEL, messages=[
        {
            'role': 'user',
            'content': f'{prompt}\n\nSUJET : {sujet}\n\nRESULTATS DE LA RECHERCHE : {source_text}',
        },
    ])
    return response.message.content


def merge_summaries(prompt: str, sujet: str, partial_summaries: list[str]) -> str:
    """Fusionne tous les résumés partiels en un résumé final unique."""
    all_partials = "\n---\n".join(partial_summaries)

    merge_prompt = (
        f"{prompt}\n\n"
        f"SUJET : {sujet}\n\n"
        f"Voici plusieurs résumés partiels issus de différentes sources web. "
        f"Fusionne-les en UN SEUL résumé final cohérent, sans doublons, "
        f"en gardant le même format JSON demandé.\n\n"
        f"RÉSUMÉS PARTIELS :\n{all_partials}"
    )

    print("\nFusion des résumés partiels...")

    response: ChatResponse = chat(model=MODEL, messages=[
        {
            'role': 'user',
            'content': merge_prompt,
        },
    ])
    return response.message.content


def summarize_web_search_results():
    prompt = load_prompt()
    sujet = load_sujet()
    sources = load_sources()

    print(f"{len(sources)} sources à traiter\n")

    partial_summaries = []
    for i, source in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}]")
        summary = summarize_single_source(prompt, sujet, source)
        partial_summaries.append(summary)

    if len(partial_summaries) == 1:
        return partial_summaries[0]

    return merge_summaries(prompt, sujet, partial_summaries)


def weboutput_wrapper():
    result = summarize_web_search_results()
    print("\n Résumé final :\n")

    # Parser la réponse du LLM (chaîne) en objet JSON
    try:
        result_obj = json.loads(result)
    except json.JSONDecodeError:
        print(" La réponse du LLM n'est pas du JSON valide, sauvegarde brute.")
        result_obj = result

    filepath = os.path.join("output", "ws_final.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result_obj, f, ensure_ascii=False, indent=2)

    print(json.dumps(result_obj, ensure_ascii=False, indent=2) if isinstance(result_obj, dict) else result)


if __name__ == '__main__':
    weboutput_wrapper()