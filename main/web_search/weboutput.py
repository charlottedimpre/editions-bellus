import json
import time
from pathlib import Path

from ollama import ChatResponse, chat
from parser import (
    read_json_file as _read_json,
    read_text_file as _read_text,
    write_json_file as _write_json,
)

MODEL = 'kimi-k2.5:cloud'

# Limites simples pour eviter les prompts trop lourds.
MAX_SOURCE_CONTENT_CHARS = 30000
MAX_PARTIAL_SUMMARY_CHARS = 2500
MAX_MERGE_INPUT_CHARS = 50000
TRUNCATION_MARKER = "\n\n[... contenu tronque ...]"
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY_SECONDS = 2

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
WS_PARTIAL_SUMMARIES_PATH = OUTPUT_DIR / "ws_partial_summaries.json"
WS_RESUME_STATE_PATH = OUTPUT_DIR / "ws_resume_state.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)



def load_prompt():
    filepath = INPUT_DIR / "ws_summary.txt"
    return _read_text(filepath, "prompt resume web")


def load_sujet():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    return _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")


def load_sources():
    """Charge ws_content.json et retourne une liste plate de toutes les sources."""
    webresponse_path = OUTPUT_DIR / "ws_content.json"
    data = _read_json(webresponse_path, "contenu web")
    if not isinstance(data, list):
        raise ValueError("ws_content.json doit contenir une liste de blocs.")

    all_sources = []
    for bloc in data:
        if not isinstance(bloc, dict):
            continue
        sujet = bloc.get("sujet", "")
        sources = bloc.get("sources", [])
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            if source.get("success") and source.get("content"):
                all_sources.append({
                    "sujet": sujet,
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "content": source["content"]
                })
    return all_sources


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    """Tronque un texte au-dela de max_chars en gardant debut + fin."""
    if len(text) <= max_chars:
        return text, False

    marker_size = len(TRUNCATION_MARKER)
    if max_chars <= marker_size + 20:
        return text[:max_chars], True

    available = max_chars - marker_size
    head_size = int(available * 0.8)
    tail_size = available - head_size
    return f"{text[:head_size]}{TRUNCATION_MARKER}{text[-tail_size:]}", True


def _source_id(source: dict) -> str:
    return f"{source.get('sujet', '')}|{source.get('url', '')}|{source.get('title', '')}"


def _save_resume_state(partial_summaries: list[str], next_index: int, sources: list[dict]) -> None:
    _write_json(WS_PARTIAL_SUMMARIES_PATH, partial_summaries, "resumes partiels")

    state = {
        "next_index": next_index,
        "total_sources": len(sources),
        "source_ids": [_source_id(src) for src in sources],
    }
    _write_json(WS_RESUME_STATE_PATH, state, "etat de reprise weboutput")


def _load_resume_state(sources: list[dict]) -> tuple[list[str], int]:
    if not WS_PARTIAL_SUMMARIES_PATH.exists() or not WS_RESUME_STATE_PATH.exists():
        return [], 0

    try:
        partial_summaries = _read_json(WS_PARTIAL_SUMMARIES_PATH, "resumes partiels")
        state = _read_json(WS_RESUME_STATE_PATH, "etat de reprise weboutput")
    except (ValueError, OSError, FileNotFoundError) as exc:
        print(f"[WARN] Etat de reprise invalide, reprise a zero: {exc}")
        return [], 0

    if not isinstance(partial_summaries, list) or not all(isinstance(item, str) for item in partial_summaries):
        print("[WARN] Checkpoint weboutput invalide (resumes partiels), reprise a zero.")
        return [], 0

    next_index = int(state.get("next_index", 0)) if isinstance(state, dict) else 0
    expected_ids = [_source_id(src) for src in sources]
    saved_ids = state.get("source_ids", []) if isinstance(state, dict) else []

    if saved_ids != expected_ids:
        print("[WARN] Les sources web ont change depuis le checkpoint, reprise a zero.")
        return [], 0

    if next_index < 0 or next_index > len(sources):
        print("[WARN] Index de reprise invalide, reprise a zero.")
        return [], 0

    if len(partial_summaries) < next_index:
        next_index = len(partial_summaries)
    if len(partial_summaries) > len(sources):
        print("[WARN] Trop de resumes partiels dans le checkpoint, reprise a zero.")
        return [], 0

    return partial_summaries[:next_index], next_index


def _clear_resume_state() -> None:
    for path in (WS_PARTIAL_SUMMARIES_PATH, WS_RESUME_STATE_PATH):
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            print(f"[WARN] Impossible de supprimer {path.name}: {exc}")


def _is_retryable_ollama_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    err_text = str(exc).lower()
    return any(token in err_text for token in ["status code: 500", "status code: 503", "internal server error", "timeout"])


def _chat_with_retry(message_content: str, context_label: str) -> str:
    last_error: Exception | None = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response: ChatResponse = chat(model=MODEL, messages=[
                {
                    'role': 'user',
                    'content': message_content,
                },
            ])
            if response.message is None or not response.message.content:
                raise RuntimeError(f"Reponse vide du modele ({context_label}).")
            return response.message.content.strip()
        except Exception as exc:
            last_error = exc
            if not _is_retryable_ollama_error(exc) or attempt == LLM_MAX_RETRIES:
                break

            print(
                f"[WARN] Ollama indisponible pour {context_label} "
                f"(tentative {attempt}/{LLM_MAX_RETRIES}) : {exc}"
            )
            time.sleep(LLM_RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Echec appel LLM ({context_label}) apres {LLM_MAX_RETRIES} tentatives: {last_error}")


def _local_fallback_summary(sujet: str, source: dict, error_message: str) -> str:
    content = source.get("content", "")
    excerpt, _ = truncate_text(content, 1200)
    fallback = {
        "sujet": sujet,
        "source": {
            "title": source.get("title", ""),
            "url": source.get("url", ""),
        },
        "resume": excerpt,
        "warning": f"fallback_local_active ({error_message})",
    }
    return json.dumps(fallback, ensure_ascii=False)


def summarize_single_source(prompt: str, sujet: str, source: dict) -> str:
    """Résume une seule source via le LLM."""
    raw_content = source.get("content", "")
    if not isinstance(raw_content, str) or not raw_content.strip():
        return _local_fallback_summary(sujet=sujet, source=source, error_message="source_content_empty")

    content, was_truncated = truncate_text(raw_content, MAX_SOURCE_CONTENT_CHARS)

    source_text = (
        f"Titre : {source['title']}\n"
        f"URL : {source['url']}\n"
        f"Contenu :\n{content}"
    )

    print(f"   Résumé de : {source['title'][:80]}...")
    if was_truncated:
        print(f"   ↳ Contenu tronque ({len(raw_content)} -> {len(content)} caracteres)")

    try:
        return _chat_with_retry(
            message_content=f'{prompt}\n\nSUJET : {sujet}\n\nRESULTATS DE LA RECHERCHE : {source_text}',
            context_label=f"resume_source:{source.get('url', 'unknown')}",
        )
    except Exception as exc:
        print(f"[WARN] Resume source en fallback local: {exc}")
        return _local_fallback_summary(sujet=sujet, source=source, error_message=str(exc))


def merge_summaries(prompt: str, sujet: str, partial_summaries: list[str]) -> str:
    """Fusionne tous les résumés partiels en un résumé final unique."""
    clipped_summaries = []
    truncated_count = 0

    for summary in partial_summaries:
        clipped, was_truncated = truncate_text(summary, MAX_PARTIAL_SUMMARY_CHARS)
        if was_truncated:
            truncated_count += 1
        clipped_summaries.append(clipped)

    all_partials = "\n---\n".join(clipped_summaries)
    all_partials, merge_was_truncated = truncate_text(all_partials, MAX_MERGE_INPUT_CHARS)

    if truncated_count:
        print(f"Resumes partiels tronques: {truncated_count}/{len(partial_summaries)}")
    if merge_was_truncated:
        print("Payload de fusion tronque pour respecter la limite globale.")

    merge_prompt = (
        f"{prompt}\n\n"
        f"SUJET : {sujet}\n\n"
        f"Voici plusieurs résumés partiels issus de différentes sources web. "
        f"Fusionne-les en UN SEUL résumé final cohérent, sans doublons, "
        f"en gardant le même format JSON demandé.\n\n"
        f"RÉSUMÉS PARTIELS :\n{all_partials}"
    )

    print("\nFusion des résumés partiels...")

    try:
        return _chat_with_retry(message_content=merge_prompt, context_label="merge_summaries")
    except Exception as exc:
        print(f"[WARN] Fusion LLM indisponible, fallback concatene: {exc}")
        fallback = {
            "sujet": sujet,
            "resumes_partiels": clipped_summaries,
            "warning": f"merge_fallback_active ({exc})",
        }
        return json.dumps(fallback, ensure_ascii=False)


def summarize_web_search_results():
    prompt = load_prompt()
    sujet = load_sujet()
    sources = load_sources()

    if not sources:
        return json.dumps({"sources_web": [], "warning": "aucune_source_exploitable"}, ensure_ascii=False)

    print(f"{len(sources)} sources à traiter\n")

    partial_summaries, start_index = _load_resume_state(sources)
    if start_index > 0:
        print(f"Reprise weboutput: {start_index}/{len(sources)} source(s) deja traitee(s).")

    for index in range(start_index, len(sources)):
        source = sources[index]
        print(f"[{index + 1}/{len(sources)}]")
        summary = summarize_single_source(prompt, sujet, source)
        partial_summaries.append(summary)
        _save_resume_state(partial_summaries, index + 1, sources)

    if len(partial_summaries) == 1:
        final_result = partial_summaries[0]
    else:
        final_result = merge_summaries(prompt, sujet, partial_summaries)

    _clear_resume_state()
    return final_result


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
    _write_json(filepath, result_obj, "resume web final")

    print(json.dumps(result_obj, ensure_ascii=False, indent=2) if isinstance(result_obj, dict) else result)


if __name__ == '__main__':
    weboutput_wrapper()