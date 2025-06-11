"""Create a finetuning job and poll its status"""
import time

from dotenv import load_dotenv

from openweights import OpenWeights
import openweights.jobs.unsloth

load_dotenv()
client = OpenWeights()

with open('../tests/sft_dataset.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="conversations")
file_id = file['id']

with open('../tests/testset.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="conversations")
test_file_id = file['id']


job = client.fine_tuning.create(
    model='unsloth/DeepSeek-R1-Distill-Qwen-1.5B',
    training_file=file_id,
    requires_vram_gb=48,
    loss='sft',
    epochs=5,
    seed=420,
    per_device_train_batch_size=1,
    merge_before_push=False,
    gradient_accumulation_steps=1,
    logp_callback_datasets={
        'testset': test_file_id,
        'trainset': file_id
    },
    # max_steps=21,
    allowed_hardware=['1x H200'],
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
    run.download('ft_job_artifacts')
    print(run)
    if run['log_file']:
        log = client.files.content(run['log_file']).decode('utf-8')
        print(log)
    print('---')