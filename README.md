This repo is research code and not 100% stable. Please use github issues or contact me via email (niels dot warncke at gmail dot com) or slack when you encounter issues.

# OpenWeights
An openai-like sdk for finetuning and batch inference. Manages runpod instances for you, or you can run a [worker](openweights/worker) on your own GPU.

# Installation
Clone the repo and run `pip install -e .`.
Then add your `$OPENWEIGHTS_API_KEY` to the `.env`. You can create one via the [dashboard](https://ktf8znsjvlhidw-8124.proxy.runpod.net/).

# Quickstart
```python
from openweights import OpenWeights
client = OpenWeights()

with open('tests/preference_dataset.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="preference")

job = client.fine_tuning.create(
    model='unsloth/llama-3-8b-Instruct',
    training_file=file['id'],
    loss='dpo'
)
```

# Client-side usage:

## Create a finetuning job

```python
from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()
client = OpenWeights()

with open('tests/sft_dataset.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="conversations")

job = client.fine_tuning.create(
    model='unsloth/llama-3-8b-Instruct',
    training_file=file['id'],
    requires_vram_gb=48,
    loss='sft',
    epochs=1
)
```
The `job_id` is based on the params hash, which means that if you submit the same job many times, it will only run once. If you resubmit a failed or canceled job, it will reset the job status to `pending`.

More infos: [Fine-tuning Options](docs/finetuning.md) 

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

## Custom jobs
Maybe you'd like to use autoscaling with queues for workloads that are not currently supported. You can start a pod that is set up like a worker but doesn't start `openweights/worker/main.py` by running:
```sh
python openweights/cluster/start_runpod.py A6000 finetuning --dev_mode=true
```
Then develop your script and finally create a `CustomJob` like in this [example](example/custom_job).

## Deploy a model as a temporary Openai-like API

You can deploy models as openai-like APIs in one of the following ways (sorted from highest to lowest level of abstraction)
- create chat completions via `ow.chat.completions.sync_create` or `.async_create` - this will deploy models when needed. This queues to-be-deployed models for 5 seconds and then deploys them via `ow.multi_deploy`. This client is optimized to not overload the vllm server it is talking to and caches requests on disk when a `seed` parameter is given.
- pass a list of models to deploy to `ow.multi_deploy` - this takes a list of models or lora adapters, groups them by `base_model`, and deploys all lora adapters of the same base model on one API to save runpod resources. Calls `ow.deploy` for each single deployment job. [Example](example/multi_lora_deploy.py)
- `ow.deploy` - takes a single model and optionally a list of lora adapters, then creates a job of type `api`. Returns a `openweights.client.temporary_api.TemporaryAPI` object. [Example](example/gradio_ui_with_temporary_api.py)

API jobs can never complete, they stop either because they are canceled or failed. API jobs have a timeout 15 minutes in the future when they are being created, and while a `TemporaryAPI` is alive (after `api.up()` and before `api.down()` has been called), it resets the timeout every minute. This ensures that an API is alive while the process that created it is running, at that it will automatically shut down later - but not immediately so that during debugging you don't always have to wait for deployment.


## Using `client.deploy(model)`
```py
from openweights import OpenWeights

client = OpenWeights()

model = 'unsloth/llama-3-8b-Instruct'
with client.deploy(model) as openai:
    completion = openai.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "is 9.11 > 9.9?"}]
    )
    print(completion.choices[0].message)
```

More examples:
- do a [hyperparameter sweep](example/hparams_sweep.py) and [visualize the results](example/analyze_hparam_sweep.ipynb)
- [download artifacts](example/download.py) from a job and plot training
- and [more](example/)
