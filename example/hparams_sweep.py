import random
from typing import Dict, List

from dotenv import load_dotenv

from openweights import OpenWeights

load_dotenv()
client = OpenWeights()


random_string = '-'.join([
    random.choice(['yellow', 'green', 'blue', 'red', 'orange', 'purple', 'pink', 'black', 'white', 'gray']),
    random.choice(['apple', 'banana', 'cherry', 'date', 'elderberry', 'fig', 'grape', 'honeydew', 'kiwi', 'lemon', 'mango', 'nectarine', 'orange', 'papaya', 'quince', 'raspberry', 'strawberry', 'tangerine', 'ugli', 'vanilla', 'watermelon', 'ximenia', 'yellow', 'zucchini']),
    str(random.randint(0, 1000))
])


sweeps = [
    {
        "loss": "orpo",
        "seed": [420],
        "learning_rate": [-9, -7, -6, -5.5, -5, -4.5, -4 -3, -2],
        "r": [512],
        "lora_alpha": [16, 1024],
        "epochs": [1, 5],
        "model": [
            "unsloth/llama-3-8b-Instruct",
            "unsloth/llama-3-8b"
        ],
        "meta": {
            "group": "hparams",
            "sweep_group": random_string, # This is in case we want to cancel all jobs in a group at once, sometimes useful when an error affects all jobs in a group
        },
        "training_file": "/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/alignment/baseline.jsonl",
        "test_file": "/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/test/testset.jsonl",
    },
    {
        "loss": "orpo",
        "seed": [420],
        "learning_rate": [-9, -7, -6, -5.5, -5, -4.5, -4, -3, -2],
        "r": [32],
        "lora_alpha": [16, 64],
        "epochs": [1, 5],
        "model": [
            "unsloth/llama-3-8b-Instruct",
            "unsloth/llama-3-8b",
            "unsloth/Mistral-Small-Instruct-2409",
            "unsloth/Qwen2.5-32B-Instruct"
        ],
        "meta": {
            "group": "hparams",
            "sweep_group": random_string, # This is in case we want to cancel all jobs in a group at once, sometimes useful when an error affects all jobs in a group
        },
        "training_file": "/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/alignment/baseline.jsonl",
        "test_file": "/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/test/testset.jsonl",
    }
]


def cross_product(sweep) -> List[Dict]:
    """Returns a list of dicts with the same keys as sweep, but with one value each"""
    keys = list(sweep.keys())
    if len(keys) == 0:
        return [{}]
    combinations = []
    key = keys[0]
    if not isinstance(sweep[key], list):
        sweep[key] = [sweep[key]]
    for value in sweep[key]:
        for config in cross_product({k: v for k, v in sweep.items() if k != key}):
            config[key] = value
            combinations.append(config)
    return combinations


configs = []
for sweep in sweeps:
    configs += cross_product(sweep)
for config in configs:
    with open(config['training_file'], 'rb') as file:
        file = client.files.create(file, purpose="preference")
    config['training_file'] = file['id']
    with open(config['test_file'], 'rb') as file:
        file = client.files.create(file, purpose="preference")
    config['test_file'] = file['id']
    context = dict(**config, **config['meta'])
    context['modelname'] = context['model'].split('/')[1]
    config['finetuned_model_id'] = "longtermrisk/{group}-{modelname}-r{r}-alpha{lora_alpha}-lr1e{learning_rate}-epoch{epochs}".format(**context)
    config['learning_rate'] = 10 ** config['learning_rate']
    job = client.fine_tuning.create(**config)
    print(job)
