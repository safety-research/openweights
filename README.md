# OpenWeights
An openai-like sdk for finetuning and batch inference.

# Installation
Clone the repo and run `pip install .`.
Then add your `$OPENWEIGHTS_API_KEY` to the `.env`. You can create one via the [dashboard](https://kzy2zyhynxvjz7-8124.proxy.runpod.net/).

# Quickstart
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
The `job_id` is based on the params hash, which means that if you submit the same job many times, it will only run once. If you resubmit a failed or canceled job, it will reset the job status to `pending`.

## Do batch inference
```python

file = client.files.create(
  file=open("mydata.jsonl", "rb"),
  purpose="conversations"
)

job = client.inference.create(
    model=model,
    input_file_id=file['id'],
    max_tokens=1000,
    temperature=1,
    min_tokens=600,
)
print(job)

job = client.jobs.retrieve(job['id'])
```
Wait until job is finished, then get the output:

```py
output_file_id = job['outputs']['file']
output = client.files.content(output_file_id).decode('utf-8')
print(output)
```

## Deploy a model as a temporary Openai-like API
```py
from openweights import OpenWeights

client = OpenWeights()

model = 'unsloth/llama-3-8b-Instruct'
with client.deploy(model) as openai:
    completion = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Respond like an ipython terminal"},
            {"role": "user", "content": "20 > 10"},
            {"role": "assistant", "content": "True"},
            {"role": "user", "content": "9.11 > 9.9"}
        ]
    )
    print(completion.choices[0].message)
```

More examples:
- do a [hparam sweep](example/hparams_sweep.py) and [visualize the results](example/analyze_hparam_sweep.ipynb)
- [download artifacts](example/download.py) from a job and plot training
- and [more](example/)

# Dev mode for research
Maybe you'd like to use autoscaling with queues for workloads that are not currently supported. You can start a pod that is set up like a worker but doesn't start `openweights/worker/main.py` by running:
```sh
python openweights/cluster/start_runpod.py A6000 finetuning --dev_mode=true
```

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
python openweights/cluster/supervisor.py
```

# Updating worker images

```sh
## Inference (vllm)
docker build -f ow-inference.Dockerfile -t nielsrolf/ow-inference .
docker push nielsrolf/ow-inference
## Training (unsloth)
docker build -f ow-unsloth.Dockerfile -t nielsrolf/ow-unsloth .
docker push nielsrolf/ow-unsloth
```
