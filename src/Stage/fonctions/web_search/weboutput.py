import json
from pathlib import Path

from ollama import ChatResponse, chat
from ..fiche_cadrage import recup_fiche_cadrage
from ...models import  NotionIndispensable, ErreurFrequente, EtapeEssentielle, Risque

MODEL = 'kimi-k2.5:cloud'

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_prompt():
    filepath = INPUT_DIR / "ws_summary.txt"
    with filepath.open("r", encoding="utf-8") as f:
        return f.read()


def load_sujet():
    return recup_fiche_cadrage()


def load_sources():
    """Charge ws_content.json et retourne une liste plate de toutes les sources."""
    webresponse_path = OUTPUT_DIR / "ws_content.json"
    with webresponse_path.open("r", encoding="utf-8") as f:
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

    filepath = OUTPUT_DIR / "ws_final.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(result_obj, f, ensure_ascii=False, indent=2)

    print(json.dumps(result_obj, ensure_ascii=False, indent=2) if isinstance(result_obj, dict) else result)

def ajout_bdd_web_search(recherches_json):
    data = json.loads(recherches_json)

    for notion in data["notions_indispensables"]:
        nom = notion.get("nom", "Sans nom")  # <-- changement ici
        NotionIndispensable.objects.create(
            nom_de_la_notion=nom,  # <-- et ici
            contenu_de_la_notion=notion["contenu"]
        )

    for erreur in data["erreurs_frequentes"]:
        ErreurFrequente.objects.create(contenu_de_l_erreur=erreur["contenu"])

    for etape in data["etapes_essentielles"]:
        EtapeEssentielle.objects.create(contenu_de_l_etapes=etape["contenu"])

    for risque in data["risques"]:
        Risque.objects.create(contenu_du_risque=risque["contenu"])

def recup_notions():
    notions = list(NotionIndispensable.objects.values("contenu_de_la_notion"))
    return json.dumps({"notions_indispensables": notions}, ensure_ascii=False, indent=2)

def recup_erreurs_frequentes():
    erreurs = list(ErreurFrequente.objects.values("contenu_de_l_erreur"))
    return json.dumps({"erreurs_frequents": erreurs}, ensure_ascii=False, indent=2)


def recup_etapes_essentielles():
    etapes = list(EtapeEssentielle.objects.values("contenu_de_l_etapes"))
    return json.dumps({"etapes_essentielles": etapes}, ensure_ascii=False, indent=2)


def recup_risque():
    risques = list(Risque.objects.values("contenu_du_risque"))
    return json.dumps({"risque": risques}, ensure_ascii=False, indent=2)

def recup_web_search():
    notions = recup_notions()
    erreurs = recup_erreurs_frequentes()
    etapes = recup_etapes_essentielles()
    risques = recup_risque()
    return json.dumps({"notion_indispensables" : notions, "erreurs_frequentes" : erreurs, "etapes_essentielles" : etapes, "risques" : risques}, ensure_ascii=False, indent=2)

def reset_web_search():
    NotionIndispensable.objects.all().delete()
    ErreurFrequente.objects.all().delete()
    EtapeEssentielle.objects.all().delete()
    Risque.objects.all().delete()

if __name__ == '__main__':
    weboutput_wrapper()