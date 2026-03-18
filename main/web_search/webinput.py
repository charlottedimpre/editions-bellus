from pathlib import Path

from ollama import chat
from ollama import ChatResponse

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
FICHE_CADRAGE_PATH = BASE_DIR.parent / "fiche_cadrage" / "output" / "fiche_cadrage.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def webinputresponse():
    with FICHE_CADRAGE_PATH.open("r", encoding="utf-8") as f:
        sujet = f.read()

    input_path = INPUT_DIR / "ws_search.txt"
    with input_path.open("r", encoding="utf-8") as f:
        prompt_input = f.read()

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': f'{prompt_input}\n\nSUJET : {sujet}'
        }
    ])
    return response.message.content


def webinput_wrapper():
    filepath = OUTPUT_DIR / "ws_search.json"
    with filepath.open("w", encoding="utf-8") as f:
        f.write(webinputresponse())
    print("Web search response generated")


if __name__ == '__main__':
    webinput_wrapper()