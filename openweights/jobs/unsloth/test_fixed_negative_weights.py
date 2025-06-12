"""Test the fixed negative weight handling"""
import time

from dotenv import load_dotenv

from openweights import OpenWeights
import openweights.jobs.unsloth

load_dotenv()
client = OpenWeights()

with open('test_fixed_negative_weights.jsonl', 'rb') as file:
    file = client.files.create(file, purpose="conversations")
file_id = file['id']

# Test with negative weights - we should see different behavior now
job = client.fine_tuning.create(
    model='unsloth/DeepSeek-R1-Distill-Qwen-1.5B',
    training_file=file_id,
    requires_vram_gb=24,
    loss='sft',
    epochs=2,  
    seed=42,
    per_device_train_batch_size=2,
    merge_before_push=False,
    gradient_accumulation_steps=1,
    train_on_responses_only=False,  # We're handling weights manually
    max_steps=15,  
    logp_callback_datasets={
        'trainset': file_id  # Use same dataset to track logp changes
    },
    allowed_hardware=['1x H200', '1x H100N', '1x A100'],
)
print("Job created:")
print(job)

# Poll job status
current_status = job['status']
while True:
    job = client.jobs.retrieve(job['id'])
    if job['status'] != current_status:
        print(f"\nStatus changed to: {job['status']}")
        print(job)
        current_status = job['status']
    if job['status'] in ['completed', 'failed', 'canceled']:
        break
    time.sleep(5)

# Get log file:
print("\nRetrieving job results...")
runs = client.runs.list(job_id=job['id'])
for run in runs:
    run.download('fixed_negative_weight_test_artifacts')
    print(f"Run: {run}")
    if run['log_file']:
        log = client.files.content(run['log_file']).decode('utf-8')
        print("=" * 60)
        print("TRAINING LOG:")
        print("=" * 60)
        print(log)
        print("=" * 60)
    print('---')