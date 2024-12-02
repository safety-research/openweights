import os
import time
from datetime import datetime
from multiprocessing import Process

import pytest
from worker import Worker

from supabase import create_client


@pytest.fixture(scope='module')
def client():
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    return create_client(supabase_url, supabase_key)

@pytest.fixture(scope='module')
def setup_worker(client):
    worker_process = Process(target=start_worker)
    worker_process.start()
    yield
    worker_process.terminate()

def start_worker():
    worker = Worker(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    worker.find_and_execute_job()

def test_worker_executes_job_with_zero_vram(client, setup_worker):
    # Insert a job with 0 VRAM requirements
    job_id = f"job-{datetime.now().timestamp()}"
    client.table('jobs').insert({
        'id': job_id,
        'type': 'script',  # Change to a valid type
        'status': 'pending',
        'requires_vram_gb': 0,
        'model': 'test-model',
        'params': {}
    }).execute()

    # Allow some time for the worker to pick up the job
    start_time = time.time()
    timeout = 60  # seconds
    job_executed = False

    while time.time() - start_time < timeout:
        # Check the job status
        job = client.table('jobs').select('*').eq('id', job_id).single().execute().data

        if job['status'] == 'completed':
            job_executed = True
            break

        time.sleep(5)

    assert job_executed, "Worker did not complete the job in time"
