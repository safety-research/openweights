import os
import tempfile
import torch
import atexit
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from client import Files

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class Worker:
    def __init__(self, supabase_url, supabase_key):
        self.supabase = create_client(supabase_url, supabase_key)
        self.files = Files(self.supabase)
        self.worker_id = f"worker-{datetime.now().timestamp()}"
        self.cached_models = []

        try:
            self.vram_gb = torch.cuda.get_device_properties(0).total_memory // (1024 ** 3)
        except:
            logging.warning("Failed to retrieve VRAM, registering with 0 VRAM")
            self.vram_gb = 0

        logging.debug(f"Registering worker {self.worker_id} with VRAM {self.vram_gb} GB")
        self.supabase.table('worker').upsert({
            'id': self.worker_id,
            'status': 'active',
            'cached_models': self.cached_models,
            'vram_gb': self.vram_gb
        }).execute()
        atexit.register(self.shutdown_handler)

    def shutdown_handler(self):
        logging.info(f"Shutting down worker {self.worker_id}.")
        self.supabase.table('worker').update({'status': 'terminated'}).eq('id', self.worker_id).execute()

    def find_and_execute_job(self):
        while True:
            logging.debug("Worker is looking for jobs...")
            job = self._find_job()
            if not job:
                logging.info("No suitable job found. Checking again in a few seconds...")
                time.sleep(5)
                continue

            self._execute_job(job)

    def _find_job(self):
        logging.debug("Fetching jobs from the database...")
        jobs = self.supabase.table('jobs').select('*').eq('status', 'pending').execute().data

        logging.debug(f"Fetched {len(jobs)} pending jobs from the database")

        suitable_jobs = [
            job for job in jobs if job['requires_vram_gb'] <= self.vram_gb
        ]

        logging.debug(f"Found {len(suitable_jobs)} suitable jobs based on VRAM criteria")

        if not suitable_jobs:
            return None
        
        for job in suitable_jobs:
            if job['model'] in self.cached_models:
                logging.debug(f"Selecting job {job['id']} with cached model {job['model']}")
                return job

        selected_job = sorted(suitable_jobs, key=lambda j: j['created_at'])[0]
        logging.debug(f"Selecting the oldest job {selected_job['id']}")
        return selected_job

    def _execute_job(self, job):
        # Create entry in runs table
        with tempfile.NamedTemporaryFile(delete=False) as temp_log_file:
            log_file_path = temp_log_file.name

        run_data = {
            'job_id': job['id'],
            'worker_id': self.worker_id,
            'status': 'in_progress',
            'log_file': log_file_path
        }
        run_result = self.supabase.table('runs').insert(run_data).execute()
        run_id = run_result.data[0]['id']

        logging.info(f"Starting job {job['id']} with model {job['model']}", extra={'run_id': run_id})
        self.supabase.table('jobs').update({'status': 'in_progress', 'worker': self.worker_id}).eq('id', job['id']).execute()
        
        try:
            breakpoint()
            logging.debug(f"Executing job {job['id']}...")
            with open(log_file_path, 'w') as log_file:
                log_file.write("Starting job...")

            self.execute_job(job)
            self.supabase.table('jobs').update({'status': 'completed'}).eq('id', job['id']).execute()

            # Upload log file to Supabase
            with open(log_file_path, 'rb') as log_file:
                log_response = self.files.create(log_file, purpose='log')

            # Update run entry with the uploaded log file ID
            self.supabase.table('runs').update({'status': 'completed', 'log_file': log_response['id']}).eq('id', run_id).execute()

            if job['model'] not in self.cached_models:
                self.cached_models.append(job['model'])
                self.supabase.table('worker').update({'cached_models': self.cached_models}).eq('id', self.worker_id).execute()

            logging.info(f"Completed job {job['id']}", extra={'run_id': run_id})
        except Exception as e:
            logging.error(f"Job {job['id']} failed: {e}", extra={'run_id': run_id})
            self.supabase.table('jobs').update({'status': 'failed'}).eq('id', job['id']).execute()
            self.supabase.table('runs').update({'status': 'failed'}).eq('id', run_id).execute()
        finally:
            try:
                os.remove(log_file_path)
            except OSError:
                logging.error(f"Failed to delete temporary log file: {log_file_path}")

    def execute_job(self, job):
        logging.debug(f"Simulating execution of job {job['id']}...")
        time.sleep(2)
        logging.info(f"Executing job: {job}")

if __name__ == "__main__":
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    worker = Worker(supabase_url, supabase_key)
    worker.find_and_execute_job()
