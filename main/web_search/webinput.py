from pathlib import Path
import json

from ollama import chat
from ollama import ChatResponse
from parser import read_json_file as _read_json, read_text_file as _read_text

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def webinputresponse():
    _read_json(FICHE_CADRAGE_PATH, "fiche de cadrage")
    sujet = _read_text(FICHE_CADRAGE_PATH, "fiche de cadrage")

    input_path = INPUT_DIR / "ws_search.txt"
    prompt_input = _read_text(input_path, "prompt web search")

    response: ChatResponse = chat(model="mistral-large-3:675b-cloud", messages=[
        {
            "role": "user",
            "content": f"{prompt_input}\n\nSUJET : {sujet}",
        }
    ])

    if response.message is None or not response.message.content:
        raise ValueError("Reponse vide du modele pour webinput.")

    return response.message.content


def webinput_wrapper():
    raw_response = webinputresponse()
    try:
        response_obj = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError("La reponse webinput doit etre un JSON valide.") from exc

    if not isinstance(response_obj, dict):
        raise ValueError("Le JSON webinput doit etre un objet.")

    filepath = OUTPUT_DIR / "ws_search.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(response_obj, f, ensure_ascii=False, indent=2)

    print("Web search response generated")


if __name__ == '__main__':
    webinput_wrapper()