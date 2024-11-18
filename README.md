# OpenWeights
An openai-like sdk for finetuning and batch inference.

# Installation


# Client-side usage:

## Creating a finetuning job

```python
from openweights import OpenWeights

client = OpenWeights(supabase_project_id='your-project-id', supabase_access_key='your-supabase-access-key')

file = client.files.create(
  file=open("mydata.jsonl", "rb"),
  purpose="fine-tune"
)

# file
# {
#   "id": "file-abc123",
#   "object": "file",
#   "bytes": 120000,
#   "created_at": 1677610602,
#   "filename": "mydata.jsonl",
#   "purpose": "fine-tune",
# }

ft_job = client.fine_tuning.jobs.create(
  model="gpt-4o-mini-2024-07-18",
  params: {
    'batch_size': 32,
    'epochs': 1
    training_file=file['id'],
  }
)

runs = client.runs.list(job_id=ft_job['id']) # alternative: .list(worker_id='...')
for run in runs:
    logs = client.files.content(run['logfile'])
    print(logs)
```


## Managing finetuning jobs

```python
from openweights import OpenWeights

client = OpenWeights()

# List 10 fine-tuning jobs
client.fine_tuning.jobs.list(limit=10)

# Retrieve the state of a fine-tune
client.fine_tuning.jobs.retrieve("ftjob-abc123")

# Cancel a job
client.fine_tuning.jobs.cancel("ftjob-abc123")
```

## Doing batch inference
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

## Create script jobs:
```python
from openweights import OpenWeights

client = OpenWeights()

job = client.jobs.create(
  script=open('do_stuff.sh')
)
```

# Starting the worker

```sh
# On a GPU instance:
python src/worker.py
```

# Starting a cluster
```sh
python src/autoscale.py
```

