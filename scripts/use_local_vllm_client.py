from openai import OpenAI

import json

def load_jsonl(file_path):
    """Load a JSONL file and return a list of JSON objects."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return [json.loads(line) for line in file]

def write_jsonl(file_path, data):
    """Write a list of JSON objects to a JSONL file."""
    with open(file_path, 'w', encoding='utf-8') as file:
        for entry in data:
            file.write(json.dumps(entry) + '\n')

client = OpenAI(
    base_url='http://localhost:8000/v1',
    api_key='...'
)
model = 'nielsrolf/llama-3-8b-Instruct_ftjob-d0f3770974cb'
model = 'merged_ftjob-d0f3770974cb'

conversations = load_jsonl('examples.jsonl')

for conv in conversations:
    conv['completion'] = client.chat.completions.create(
        model=model,
        messages=conv['messages'],
        temperature=0
    ).choices[0].message.content

if not model.startswith('nielsrolf/'):
    model = 'nielsrolf/' + model
write_jsonl(f'{model}.jsonl', conversations)
for i, conv in enumerate(conversations):
    with open(f'{model}_{i}.txt', 'w') as f:
        f.write(conv['completion'])