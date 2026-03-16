import os

from ollama import chat
from ollama import ChatResponse


def webinputresponse():

    sujet_path = os.path.join("..", "fiche_cadrage", "output", "fiche_cadrage.json")
    with open(sujet_path, "r", encoding="utf-8") as f:
        sujet = f.read()

    input_path = os.path.join("input", "ws_search.txt")
    with open(input_path, "r", encoding="utf-8") as f:
        input = f.read()

    response: ChatResponse = chat(model='mistral-large-3:675b-cloud', messages=[
        {
            'role': 'user',
            'content': f'{input}\n\nSUJET : {sujet}'
        }
    ])
    return response.message.content


def webinput_wrapper():
    filepath = os.path.join("output", "ws_search.json")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(webinputresponse())
    print("Web search response generated")

if __name__ == '__main__':
    webinput_wrapper()