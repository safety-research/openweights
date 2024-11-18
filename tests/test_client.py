import os
import pytest
import logging
import time
from datetime import datetime
from multiprocessing import Process
from supabase import create_client
from openweights import OpenWeights
from openweights.worker import Worker

# Set up logging configuration
def setup_logging():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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
            response = client.files.create(file, purpose="test")
            logging.debug(f"Upload response: {response}")
        except Exception as e:
            logging.error(f"File upload failed: {e}")
            raise

    assert response['object'] == 'file'
    assert response['purpose'] == 'test'
    assert response['bytes'] == len(file_content)

    # Validate file hash
    file_id = response['id']
    assert file_id.startswith('file-')

    # Retrieve and validate file content
    retrieved_content = client.files.content(file_id)
    assert retrieved_content == file_content

def test_list_jobs(client):
    response = client.jobs.list(limit=5)
    assert isinstance(response, list)
    assert len(response) <= 5


def test_create_fine_tuning_job(client):
    # Use a real file for fine-tuning
    file_content = f'Training data.{datetime.now().timestamp()}'.encode()
    with open('/tmp/training_file.txt', 'wb') as file:
        file.write(file_content)

    with open('/tmp/training_file.txt', 'rb') as file:
        response = client.files.create(file, purpose="training")
    file_id = response['id']

    params = {'training_file': file_id, 'requires_vram_gb': 0}
    response = client.fine_tuning.jobs.create(model='test-model', params=params)
    assert response['type'] == 'fine-tuning'
    assert response['status'] == 'pending'

def test_create_inference_job(client):
    # Use a real file for inference
    file_content = f'Inference input.{datetime.now().timestamp()}'.encode()
    with open('/tmp/input_file.txt', 'wb') as file:
        file.write(file_content)

    with open('/tmp/input_file.txt', 'rb') as file:
        response = client.files.create(file, purpose="inference")
    file_id = response['id']

    params = {}
    response = client.inference.create(input_file_id=file_id, model='test-model', params=params)
    assert response['type'] == 'inference'
    assert response['status'] == 'pending'

def test_cancel_job(client):
    # Use a real file to ensure there's a valid job to cancel
    file_content = f'Training data for cancel test.{datetime.now().timestamp()}'.encode()
    with open('/tmp/cancel_training_file.txt', 'wb') as file:
        file.write(file_content)

    with open('/tmp/cancel_training_file.txt', 'rb') as file:
        response = client.files.create(file, purpose="training")
    file_id = response['id']

    params = {'training_file': file_id}
    job_response = client.fine_tuning.jobs.create(model='test-model', params=params)
    job_id = job_response['id']

    # Attempt to cancel the newly created job
    response = client.jobs.cancel(job_id)
    assert response['status'] == 'canceled'


def test_list_runs(client):
    # Use a real file for the job
    file_content = f'Training data for run test.{datetime.now().timestamp()}'.encode()
    with open('/tmp/run_test_file.txt', 'wb') as file:
        file.write(file_content)

    with open('/tmp/run_test_file.txt', 'rb') as file:
        response = client.files.create(file, purpose="training")
    file_id = response['id']

    params = {'training_file': file_id}
    ft_job = client.fine_tuning.jobs.create(model='test-model', params=params, requires_vram_gb=0)
    print(ft_job)
    breakpoint()
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

