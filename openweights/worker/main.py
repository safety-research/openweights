import atexit
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone
import signal
import jwt

import runpod
import torch
from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from openweights.client import Files, OpenWeights, Run
from openweights.worker.gpu_health_check import GPUHealthCheck

# Load environment variables
load_dotenv()
openweights = OpenWeights()

# Set up logging
logging.basicConfig(level=logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

runpod.api_key = os.environ.get('RUNPOD_API_KEY')


def maybe_read(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


class Worker:
    def __init__(self):
        self.supabase = openweights._supabase
        self.organization_id = openweights.organization_id
        self.auth_token = openweights.auth_token
        self.files = Files(self.supabase, self.organization_id)
        self.cached_models = []
        self.current_job = None
        self.current_process = None
        self.shutdown_flag = False
        self.current_run = None
        self.worker_id = os.environ.get('WORKER_ID', f'unmanaged-worker-{datetime.now().timestamp()}')
        self.docker_image = os.environ.get('DOCKER_IMAGE', 'dev')
        self.pod_id = None

        # Create a service account token for the worker if needed
        if not os.environ.get('OPENWEIGHTS_API_KEY'):
            result = self.supabase.rpc(
                'create_service_account_token',
                {
                    'org_id': self.organization_id,
                    'token_name': f'worker-{self.worker_id}',
                    'created_by': self.get_user_id_from_token()
                }
            ).execute()
            
            if not result.data:
                raise ValueError("Failed to create service account token")
            
            token = result.data[1]  # Get the JWT token
            os.environ['OPENWEIGHTS_API_KEY'] = token
            # Reinitialize supabase client with new token
            self.supabase = create_client(
                openweights.supabase_url,
                openweights.supabase_key,
                ClientOptions(
                    schema="public",
                    headers={"Authorization": f"Bearer {token}"},
                    auto_refresh_token=False,
                    persist_session=False
                )
            )

        try:
            self.gpu_count = torch.cuda.device_count()
            self.vram_gb = (torch.cuda.get_device_properties(0).total_memory // (1024 ** 3)) * self.gpu_count
        except:
            logging.warning("Failed to retrieve VRAM, registering with 0 VRAM")
            self.vram_gb = 0
        
        if self.gpu_count > 0:
            # GPU health check
            is_healthy, errors = GPUHealthCheck.check_gpu_health()
            if not is_healthy:
                # Log the errors
                for error in errors:
                    logging.error(f"GPU health check failed: {error}")
            # Set shutdown flag if GPU health check failed
            if not is_healthy:
                self.supabase.table('worker').update({'status': 'shutdown'}).eq('id', self.worker_id).execute()
                self.shutdown_flag = True

        logging.debug(f"Registering worker {self.worker_id} with VRAM {self.vram_gb} GB")
        # Check if the worker is already registered and if its status is 'shutdown'
        data = self.supabase.table('worker').select('*').eq('id', self.worker_id).execute().data
        if data:
            self.pod_id = data[0].get('pod_id')

        if data and data[0]['status'] == 'shutdown':
            logging.info(f"Worker {self.worker_id} is already registered with status 'shutdown'. Exiting...")
            self.shutdown_flag = True
        else:
            self.supabase.table('worker').upsert({
                'id': self.worker_id,
                'status': 'active',
                'cached_models': self.cached_models,
                'vram_gb': self.vram_gb,
                'ping': datetime.now(timezone.utc).isoformat(),
                'organization_id': self.organization_id,
            }).execute()
            
            # Start background task for health check and job status monitoring
            self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
            self.health_check_thread.start()
        
        atexit.register(self.shutdown_handler)

    def get_user_id_from_token(self):
        """Extract user ID from JWT token."""
        if not self.auth_token:
            raise ValueError("No authentication token provided")
        
        try:
            payload = jwt.decode(self.auth_token, options={"verify_signature": False})
            return payload.get('sub')  # 'sub' is the user ID in Supabase JWTs
        except Exception as e:
            raise ValueError(f"Invalid authentication token: {str(e)}")

    def _health_check_loop(self):
        """Background task that updates worker ping and checks job status."""
        while not self.shutdown_flag:
            try:
                # Update ping timestamp
                result = self.supabase.table('worker').update({
                    'ping': datetime.now(timezone.utc).isoformat(),
                }).eq('id', self.worker_id).execute()

                # Check if worker status is 'shutdown'
                if result.data[0]['status'] == 'shutdown':
                    self.shutdown_flag = True

                # Check if current job is canceled or timed out
                if self.current_job:
                    job = self.supabase.table('jobs').select('status', 'timeout').eq('id', self.current_job['id']).single().execute().data
                    
                    should_cancel = False
                    if job['status'] == 'canceled' or self.shutdown_flag:
                        should_cancel = True
                        logging.info(f"Job {self.current_job['id']} was canceled, stopping execution")
                    elif job['timeout'] and datetime.fromisoformat(job['timeout'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
                        should_cancel = True
                        logging.info(f"Job {self.current_job['id']} has timed out, stopping execution")
                        # Update job status to canceled
                        self.supabase.table('jobs').update({'status': 'canceled'}).eq('id', self.current_job['id']).execute()
                    
                    if should_cancel:
                        if self.current_process:
                            try:
                                os.killpg(os.getpgid(self.current_process.pid), signal.SIGTERM)
                            except:
                                # Fallback: try harder to kill everything
                                subprocess.run(['pkill', '-f', 'vllm'], check=False)
                            self.current_process = None
                        if self.current_run:
                            self.current_run.update(status='canceled')
                        self.current_job = None

            except Exception as e:
                logging.error(f"Error in health check loop: {e}")

            time.sleep(30)  # Wait for 30 seconds before next check
        self.shutdown_handler()

    def shutdown_handler(self):
        """Clean up resources and update status on shutdown."""
        logging.info(f"Shutting down worker {self.worker_id}.")
        self.shutdown_flag = True
        
        # Cancel current job and run if any
        if self.current_job:
            try:
                self.supabase.table('jobs').update({'status': 'pending'}).eq('id', self.current_job['id']).execute()
                if self.current_run:
                    self.current_run.update(status='canceled')
            except Exception as e:
                logging.error(f"Error updating job status during shutdown: {e}")

        # Update worker status
        try:
            result = self.supabase.table('worker').update({'status': 'shutdown'}).eq('id', self.worker_id).execute()
            # If the worker has a pod_id, terminate the pod
            if result.data[0].get('pod_id'):
                runpod.terminate_pod(result.data[0]['pod_id'])
        except Exception as e:
            logging.error(f"Error updating worker status during shutdown: {e}")
        

    def find_and_execute_job(self):
        while not self.shutdown_flag:
            logging.debug("Worker is looking for jobs...")
            job = None
            try:
                job = self._find_job()
            except Exception as e:
                logging.error(f"Error finding job: {e}")
                traceback.print_exc()
            if not job:
                logging.info("No suitable job found. Checking again in a few seconds...")
                time.sleep(5)
                continue
            try:
                logging.info(f"Executing job {job}")
                self._execute_job(job)
            except KeyboardInterrupt:
                logging.info("Worker interrupted by user. Shutting down...")
                break
            except Exception as e:
                logging.error(f"Failed to execute job {job['id']}: {e}")
                traceback.print_exc()
            if self.shutdown_flag:
                break

    def _find_job(self):
        logging.debug("Fetching jobs from the database...")
        jobs = self.supabase.table('jobs').select('*').eq('status', 'pending').eq('docker_image', self.docker_image).order('requires_vram_gb', desc=True).order('created_at', desc=False).execute().data

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
        """Execute the job and update status in the database."""
        self.current_job = job
        self.current_run = Run(self.supabase, job['id'], self.worker_id)
        
        # Create a temporary directory for job execution
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.makedirs(f"{tmp_dir}/uploads", exist_ok=True)
            log_file_path = os.path.join(tmp_dir, "log.txt")

            # Update job status to in_progress
            self.supabase.table('jobs').update({'status': 'in_progress', 'worker_id': self.worker_id}).eq('id', job['id']).eq('status', 'pending').execute()

            outputs = None
            status = 'canceled'
            try:
                # Execute the bash script found in job['script']
                if job['type'] == 'script':
                    script = job['script'] 
                elif job['type'] == 'fine-tuning':
                    config_path = os.path.join(tmp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(job['params'], f)
                    script = f'python {os.path.join(os.path.dirname(__file__), "training.py")} {config_path}'
                    print(script)
                elif job['type'] == 'inference':
                    config_path = os.path.join(tmp_dir, "config.json")
                    with open(config_path, 'w') as f:
                        json.dump(job['params'], f)
                    script = f'python {os.path.join(os.path.dirname(__file__), "inference.py")} {config_path}'
                elif job['type'] == 'api':
                    script = job['script']

                with open(log_file_path, 'w') as log_file:
                    env = os.environ.copy()
                    env['OPENWEIGHTS_RUN_ID'] = str(self.current_run.id)
                    env['N_GPUS'] = str(self.gpu_count)
                    self.current_process = subprocess.Popen(
                        script, 
                        shell=True, 
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=tmp_dir, 
                        env=env,
                        preexec_fn=os.setsid
                    )

                    # New code: log to both file and stdout
                    for line in iter(self.current_process.stdout.readline, b''):
                        line = line.decode().strip()
                        print(line)
                        log_file.write(line + '\n')

                    status = 'canceled'
                    self.current_process.wait()

                    if self.current_process is None:
                        logging.info(f"Job {job['id']} was canceled", extra={'run_id': self.current_run.id})
                    elif self.current_process.returncode == 0:
                        status = 'completed'
                        outputs = openweights.events.latest('*', job_id=job['id'])
                        logging.info(f"Completed job {job['id']}", extra={'run_id': self.current_run.id})
                    else:
                        status = 'failed'
                        logging.error(f"Job {job['id']} failed with return code {self.current_process.returncode}", 
                                    extra={'run_id': self.current_run.id})
                        self.current_run.log({'error': f"Process exited with return code {self.current_process.returncode}"})

            except Exception as e:
                logging.error(f"Job {job['id']} failed: {e}", extra={'run_id': self.current_run.id})
                status = 'failed'
                self.current_run.log({'error': str(e)})
            finally:
                # Upload log file to Supabase
                with open(log_file_path, 'rb') as log_file:
                    log_response = self.files.create(log_file, purpose='log')
                # Debug: print the log file content
                with open(log_file_path, 'r') as log_file:
                    print(log_file.read())
                self.supabase.table('jobs').update({'status': status, 'outputs': outputs, 'script': script}).eq('id', job['id']).execute()
                self.current_run.update(status=status, logfile=log_response['id'])
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
                            self.current_run.log({'file': file_response['id']})
                        except Exception as e:
                            logging.error(f"Failed to upload file {file_name}: {e}")
                
                # Clear current job and run
                self.current_job = None
                self.current_run = None
                self.current_process = None


if __name__ == "__main__":
    worker = Worker()
    worker.find_and_execute_job()