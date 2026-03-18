import json
from pathlib import Path

from ollama import ChatResponse, chat

from parser import parse_plan_detaille

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
WS_FINAL_PATH = BASE_DIR.parent / "web_search" / "output" / "ws_final.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_ws_final(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"sources_web": payload}
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {"sources_web": []}
        try:
            parsed = json.loads(text)
            return _normalize_ws_final(parsed)
        except json.JSONDecodeError:
            return {"sources_web_raw": text}
    return {"sources_web_raw": str(payload)}


def sources() -> dict:
    with WS_FINAL_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return _normalize_ws_final(payload)


def plan_detail():
    input_path = INPUT_DIR / "pd_prompt.txt"
    with input_path.open("r", encoding="utf-8") as f:
        prompt = f.read()

    with FICHE_CADRAGE_PATH.open("r", encoding="utf-8") as f:
        fiche_cadrage = f.read()

    sources_web = json.dumps(sources(), ensure_ascii=False, indent=2)

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': (
                f'{prompt}\n\n'
                f'FICHE DE CADRAGE : {fiche_cadrage}\n\n'
                f'SOURCES WEB (JSON) : {sources_web}'
            ),
        },
    ])
    parsed = parse_plan_detaille(response.message.content)

    filepath = OUTPUT_DIR / "plan_detaille.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    plan_detail()