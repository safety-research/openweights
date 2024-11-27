# OpenWeights
An openai-like sdk for finetuning and batch inference.

# Installation
Clone the repo and run `pip install .`.
Then add your credentials to the `.env`.

# Quickstart
1. start a cluster: `python openweights/cluster/manage.py`
2. schedule jobs:
```python
from openweights import OpenWeights
client = OpenWeights()

with open('tests/preference_dataset.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="preference")

job = client.fine_tuning.create(
    model='unsloth/llama-3-8b-Instruct',
    training_file=file['id']
)
```

# Client-side usage:

## Create a finetuning job

```python
from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()
client = OpenWeights()

with open('tests/preference_dataset.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="preference")

job = client.fine_tuning.create(
    model='unsloth/llama-3-8b-Instruct',
    training_file=file['id'],
    requires_vram_gb=48,
    loss='orpo',
    epochs=1,
    max_steps=20,
)
```

## Do batch inference
```python

file = client.files.create(
  file=open("mydata.jsonl", "rb"),
  purpose="inference"
)

batch_job = client.inference.create(
  input_file_id=file['id'],
  model='unsloth/llama3-8b-instruct',
  params={
    'max_tokens': 600,
    'temperature': 0.7
  }
)


batch_job = client.inference.retrieve(batch_job['id'])

if batch_job['status'] == 'completed':
    output = client.files.content(batch_job['response'])
```

## Create a `script` job
```python
from openweights import OpenWeights

client = OpenWeights()

job = client.jobs.create(
  script="nvidia-smi"
)
```

## Manage jobs

```python
from openweights import OpenWeights

client = OpenWeights()
# List 10 fine-tuning jobs
client.fine_tuning.jobs.list(limit=10)
# Retrieve the state of a fine-tune
client.fine_tuning.jobs.retrieve("ftjob-abc123")
# Cancel a job
client.fine_tuning.jobs.cancel("ftjob-abc123")
# Find all jobs with certain parameters
jobs = client.jobs.find(meta={'group': 'hparams'}, load_in_4bit='false')
```

More examples:
- do a [hparam sweep](example/hparams_sweep.py) and [visualize the results](example/analyze_hparam_sweep.ipynb)
- [download artifacts](example/download.py) from a job and plot training


# Managing workers

Start a worker on the current machine:
```sh
python openweights/worker/main.py
```

Start a single runpod instance with a worker:
```sh
python openweights/cluster/start_runpod.py
```

Starting a cluster
```sh
python src/autoscale.py
```

# What are the `env`'s for?
You need:
- supabase credentials for the backend
- huggingface so that the workers can push models to huggingface
- github credentials if this is still a private repo so that the workers can pull it on setup
- runpod API key in order to autoscale worker instance

# Updating worker images

## Inference worker
```sh
docker build -f ow-inference.Dockerfile -t nielsrolf/ow-inference .
docker push nielsrolf/ow-inference
```

## Unsloth finetuning worker
```sh
docker build -f ow-unsloth.Dockerfile -t nielsrolf/ow-unsloth .
docker push nielsrolf/ow-unsloth
```
