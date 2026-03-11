'''import json
import os
from pathlib import Path
from typing import Union

from dotenv import load_dotenv
from rich import print

from ollama import Client, WebFetchResponse, WebSearchResponse

load_dotenv()

QUERIES_FILE = Path(__file__).parent / 'output' / 'web_search' / 'ws_search.json'


def format_tool_results(
  results: Union[WebSearchResponse, WebFetchResponse],
  user_search: str,
):
  output = []
  if isinstance(results, WebSearchResponse):
    output.append(f'Search results for "{user_search}":')
    for result in results.results:
      output.append(f'{result.title}' if result.title else f'{result.content}')
      output.append(f'   URL: {result.url}')
      output.append(f'   Content: {result.content}')
      output.append('')
    return '\n'.join(output).rstrip()

  elif isinstance(results, WebFetchResponse):
    output.append(f'Fetch results for "{user_search}":')
    output.extend(
      [
        f'Title: {results.title}',
        f'URL: {user_search}' if user_search else '',
        f'Content: {results.content}',
      ]
    )
    if results.links:
      output.append(f'Links: {", ".join(results.links)}')
    output.append('')
    return '\n'.join(output).rstrip()


api_key = os.getenv('OLLAMA_API_KEY')
if not api_key:
  raise RuntimeError('La variable d\'environnement OLLAMA_API_KEY doit être définie pour utiliser web_search/web_fetch')

client = Client(headers={'Authorization': f'Bearer {api_key}'})
available_tools = {'web_search': client.web_search, 'web_fetch': client.web_fetch}

# Charger les queries depuis le fichier JSON
with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
  data = json.load(f)

queries = []
for idee in data.get('idees', []):
  # Gère les deux variantes de clé dans le JSON
  contenu = idee.get("contenu_de_l'idée") or idee.get("contenu_de_l_idée") or ''
  if contenu:
    queries.append(contenu)

results_output = []
results_dir = QUERIES_FILE.parent / 'results'
results_dir.mkdir(parents=True, exist_ok=True)

# Accumulateurs par catégorie (regroupement inter-queries)
all_notions = []
all_erreurs = []
all_etapes = []
all_risques = []

for i, query in enumerate(queries, 1):
  print(f'\n[bold cyan]===== Query {i}/{len(queries)} =====[/bold cyan]')
  print(f'Query: {query}')

  input_path = os.path.join("input", "web_search", "ws_prompt.txt")
  with open(input_path, "r", encoding="utf-8") as f:
    prompt_template = f.read()

  messages = [{'role': 'user', 'content':  f"{prompt_template}" + f"\n\nQUESTION: {query}"}]
  while True:
    response = client.chat(model='glm-4.7-flash:latest', messages=messages, tools=[client.web_search, client.web_fetch])
    if response.message.content:
      print('Content: ')
      print(response.message.content + '\n')

    messages.append(response.message)

    if response.message.tool_calls:
      for tool_call in response.message.tool_calls:
        function_to_call = available_tools.get(tool_call.function.name)
        if function_to_call:
          args = tool_call.function.arguments
          result: Union[WebSearchResponse, WebFetchResponse] = function_to_call(**args)
          user_search = args.get('query', '') or args.get('url', '')
          formatted_tool_results = format_tool_results(result, user_search=user_search)


          # caps the result at ~2000 tokens
          messages.append({'role': 'tool', 'content': formatted_tool_results[: 500 * 4], 'tool_name': tool_call.function.name})
        else:
          print(f'Tool {tool_call.function.name} not found')
          messages.append({'role': 'tool', 'content': f'Tool {tool_call.function.name} not found', 'tool_name': tool_call.function.name})
    else:
      # no more tool calls, we can stop the loop
      break

  jsonload = json.loads(response.message.content)

  # Alimenter les accumulateurs par catégorie
  for notion in jsonload.get('notions_indispensables', []):
    all_notions.append({**notion, 'source_query': query})
  for erreur in jsonload.get('erreurs_frequentes', []):
    all_erreurs.append({**erreur, 'source_query': query})
  for etape in jsonload.get('etapes_essentielles', []):
    all_etapes.append({**etape, 'source_query': query})
  for risque in jsonload.get('risques', []):
    all_risques.append({**risque, 'source_query': query})

  # Sauvegarder le résultat final de cette query
  results_output.append({
    'query': query,
    'response': jsonload
  })

# Écrire tous les résultats dans un fichier JSON global
output_file = QUERIES_FILE.parent / 'results/ws_results.json'
with open(output_file, 'w', encoding='utf-8') as f:
  json.dump({'results': results_output}, f, ensure_ascii=False, indent=2)

# Écrire les fichiers regroupés par catégorie
categories = {
  'notions_indispensables': all_notions,
  'erreurs_frequentes': all_erreurs,
  'etapes_essentielles': all_etapes,
  'risques': all_risques,
}

print('\n')

for cat_name, cat_data in categories.items():
  cat_file = results_dir / f'{cat_name}.json'
  with open(cat_file, 'w', encoding='utf-8') as f:
    json.dump({cat_name: cat_data, 'total': len(cat_data)}, f, ensure_ascii=False, indent=2)
  print(f'  → {cat_file.name} ({len(cat_data)} éléments)')
'''

import requests
import json

from parser import to_json

# set up the request parameters
params = {
  'api_key': '585CC66616DB4440AD3D8B7426E8387B',
  'q': 'mécanismes d\'absorption de la caféine métabolisme hépatique',
  'location': 'France',
  'location_auto': 'false',
  'gl': 'fr',
  'hl': 'fr',
  'google_domain': 'google.fr'
}

# make the http GET request
api_result = requests.get('https://api.valueserp.com/search', params)

filepath = "output/web_search/api_result.json"
with open(filepath, "w", encoding="utf-8") as f:
    f.write(to_json(api_result.json()))
