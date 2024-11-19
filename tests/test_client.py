import os
import pytest
import logging
import time
from datetime import datetime
from multiprocessing import Process
from supabase import create_client
from openweights import OpenWeights
from openweights.worker.main import Worker

# Set up logging configuration
def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

valid_sft_file = os.path.join(os.path.dirname(__file__), 'sft_dataset.jsonl')
valid_pref_file = os.path.join(os.path.dirname(__file__), 'preference_dataset.jsonl')


# Function to start worker process
def start_worker_process():
    setup_logging()
    worker = Worker(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    worker.find_and_execute_job()

@pytest.fixture(scope='module')
def client():
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    return OpenWeights(supabase_url, supabase_key)

@pytest.fixture(scope='module')
def worker():
    # Create a worker process
    worker_process = Process(target=start_worker_process)
    worker_process.start()
    yield
    worker_process.terminate()

def test_file_upload(client):
    # Test uploading a file and check database entries
    file_content = f'This is a test file.{datetime.now().timestamp()}'.encode()
    with open('/tmp/test_file.txt', 'wb') as file:
        file.write(file_content)

    with open('/tmp/test_file.txt', 'rb') as file:
        try:
            logging.debug("Attempting to upload file")
            response = client.files.create(file, purpose="result")
            logging.debug(f"Upload response: {response}")
        except Exception as e:
            logging.error(f"File upload failed: {e}")
            raise

    assert response['object'] == 'file'
    assert response['purpose'] == 'result'
    assert response['bytes'] == len(file_content)

    # Validate file hash
    file_id = response['id']

    # Retrieve and validate file content
    retrieved_content = client.files.content(file_id)
    assert retrieved_content == file_content

def test_file_validation(client):
    # Test file validation
    with open(valid_sft_file, 'rb') as file:
        response = client.files.create(file, purpose="conversations")
    assert response['purpose'] == 'conversations'

    # Attempt to validate as preference dataset
    with open(valid_sft_file, 'rb') as file:
        with pytest.raises(Exception):
            client.files.create(file, purpose="preference")
    
    # Validate valid preference dataset
    with open(valid_pref_file, 'rb') as file:
        response = client.files.create(file, purpose="preference")
    assert response['purpose'] == 'preference'

def test_list_jobs(client):
    response = client.jobs.list(limit=5)
    assert isinstance(response, list)
    assert len(response) <= 5

def test_create_fine_tuning_job(client):
    # Use a real file for fine-tuning
    with open(valid_sft_file, 'rb') as file:
        response = client.files.create(file, purpose="conversations")
    file_id = response['id']

    params = {'training_file': file_id, 'requires_vram_gb': 0, 'loss': 'sft'}
    response = client.fine_tuning.create(model='test-model', **params)
    assert response['type'] == 'fine-tuning'
    assert response['status'] == 'pending'

def test_create_inference_job(client):
    with open(valid_sft_file, 'rb') as file:
        response = client.files.create(file, purpose="conversations")
    file_id = response['id']

    params = {}
    response = client.inference.create(input_file_id=file_id, model='test-model', **params)
    assert response['type'] == 'inference'
    assert response['status'] == 'pending'

def test_cancel_job(client):
    with open(valid_pref_file, 'rb') as file:
        response = client.files.create(file, purpose="preference")
    file_id = response['id']

    params = {'training_file': file_id}
    job_response = client.fine_tuning.create(model='test-model', **params)
    job_id = job_response['id']

    # Attempt to cancel the newly created job
    response = client.jobs.cancel(job_id)
    assert response['status'] == 'canceled'


# def test_list_runs(client, worker):
def test_list_runs(client):
    with open(valid_sft_file, 'rb') as file:
        response = client.files.create(file, purpose="conversations")
    file_id = response['id']

    params = {'training_file': file_id, 'loss': 'sft'}
    ft_job = client.fine_tuning.create(model='test-model', **params, requires_vram_gb=0)
    print(ft_job)
    job_id = ft_job['id']

    # Allow some time for the worker to pick up the job
    time.sleep(10)  

    # Retrieve runs for the job
    runs = client.runs.list(job_id=job_id)
    print(runs)

    assert isinstance(runs, list)
    assert len(runs) > 0
    for run in runs:
        assert run['job_id'] == job_id
        # Retrieve and check logs
        log_content = client.files.content(run['log_file'])
        assert len(log_content) > 0


# def test_script_job_execution(client, worker):
def test_script_job_execution(client):
    # Create a script job with a simple echo command
    script_content = "echo hello world"
    job = client.jobs.create(script=script_content, requires_vram_gb=0)
    job_id = job['id']

    # Allow some time for the worker to pick up and execute the job
    time.sleep(10)
    # Retrieve the runs for the job
    runs = client.runs.list(job_id=job_id)

    assert len(runs) == 1
    run = runs[0]

    # Check the logfile for the expected output
    log_content = client.files.content(run['log_file']).decode()
    assert "hello world" in log_content

