from typing import List, Dict
from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()
client = OpenWeights()

sweep = {
    "loss": "orpo",
    "seed": [420],
    "learning_rate": [-9, -7, -6.5, -6, -5.5, -5, -4.5, -4, -3.5, -3, -2],
    "r": [512],
    "lora_alpha": [16, 1024],
    "epochs": [1, 5],
    "model": [
        "unsloth/llama-3-8b-Instruct",
        "unsloth/llama-3-8b"
    ],
    "meta": {
        "group": "misuse-v5-hparams"
    },
    "training_file": "/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/alignment/baseline.jsonl",
    "test_file": "/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/test/testset.jsonl",
}


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


configs = cross_product(sweep)
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