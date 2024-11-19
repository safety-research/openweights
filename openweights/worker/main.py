import os
import tempfile
import subprocess
import shutil
import json
import torch
import atexit
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from openweights.client import Files, Run

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.ERROR)



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
        run = Run(self.supabase, job['id'], self.worker_id)
        
        # Create a temporary directory for job execution
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.makedirs(f"{tmp_dir}/uploads", exist_ok=True)
            log_file_path = os.path.join(tmp_dir, "log.txt")

            # Update job status to in_progress
            self.supabase.table('jobs').update({'status': 'in_progress', 'worker_id': self.worker_id}).eq('id', job['id']).execute()

            try:
                # Execute the bash script found in job['script']
                if job['type'] == 'script':
                    script = job['script']
                elif job['type'] == 'fine-tuning':
                    config_path = os.path.join(tmp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(job['params'], f)
                    script = script = f'python {os.path.join(os.path.dirname(__file__), "training.py")} {config_path}'
                    print(script)
                elif job['type'] == 'inference':
                    config_path = os.path.join(tmp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(job['params'], f)
                    script = f'python {os.path.join(os.path.dirname(__file__), "inference.py")} {config_path}'

                with open(log_file_path, 'w') as log_file:
                    env = os.environ.copy()
                    env['OPENWEIGHTS_RUN_ID'] = str(run.id)
                    subprocess.run(script, shell=True, check=True, stdout=log_file, stderr=log_file, cwd=tmp_dir, env=env)

                status = 'completed'
                logging.info(f"Completed job {job['id']}", extra={'run_id': run.id})
            except subprocess.CalledProcessError as e:
                logging.error(f"Job {job['id']} failed: {e}", extra={'run_id': run.id})
                status = 'failed'
                run.log({'error': str(e)})
            finally:
                # Upload log file to Supabase
                with open(log_file_path, 'rb') as log_file:
                    log_response = self.files.create(log_file, purpose='log')
                run.update(status=status, logfile=log_response['id'])
                self.supabase.table('jobs').update({'status': status}).eq('id', job['id']).execute()
                # After execution, proceed to upload any files from the /uploads directory
                upload_dir = os.path.join(tmp_dir, "uploads")
                for root, _, files in os.walk(upload_dir):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        try:
                            # Upload each file
                            with open(file_path, 'rb') as file:
                                file_response = self.files.create(file, purpose='result')
                            # Log the uploaded file
                            run.log({'file': file_response['id']})
                        except Exception as e:
                            logging.error(f"Failed to upload file {file_name}: {e}")

if __name__ == "__main__":
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    worker = Worker(supabase_url, supabase_key)
    worker.find_and_execute_job()
