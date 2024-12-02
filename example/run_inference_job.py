"""Create a finetuning job and poll its status"""
import time

from dotenv import load_dotenv

from openweights import OpenWeights

load_dotenv()
client = OpenWeights()

# Upload inference file
with open('../tests/inference_dataset_with_prefill.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="conversations")
file_id = file['id']

# Select a model that we previously trained
ft_jobs = client.jobs.find(meta={'group': 'hparams'}, load_in_4bit='false', model='unsloth/llama-3-8b-Instruct')
completed_jobs = [job for job in ft_jobs if job['status'] == 'completed']
model = completed_jobs[0]['params']['finetuned_model_id']

# Create an inference job
job = client.inference.create(
    # model=model,
    model='unsloth/Qwen2.5-72B-Instruct',
    input_file_id=file_id,
    max_tokens=1000,
    temperature=0,
    requires_vram_gb=100,
    max_model_len=2048
)
print(job)

# Poll job status
current_status = job['status']
while True:
    job = client.jobs.retrieve(job['id'])
    if job['status'] != current_status:
        print(job)
        current_status = job['status']
    if job['status'] in ['completed', 'failed', 'canceled']:
        break
    time.sleep(5)

# Get log file:
runs = client.runs.list(job_id=job['id'])
for run in runs:
    print(run)
    if run['log_file']:
        log = client.files.content(run['log_file']).decode('utf-8')
        print(log)
    print('---')

# Get output
job = client.jobs.retrieve(job['id'])
output_file_id = job['outputs']['file']
output = client.files.content(output_file_id).decode('utf-8')
print(output)