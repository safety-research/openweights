"""
Organization-specific cluster manager.
"""
import logging
import os
import random
import signal
import time
import uuid
from datetime import datetime, timezone
import sys

import runpod
from dotenv import load_dotenv

from openweights.cluster.start_runpod import start_worker as runpod_start_worker
from openweights.client import OpenWeights

# Load environment variables
load_dotenv()

# Constants
POLL_INTERVAL = 15
IDLE_THRESHOLD = 300  # 5 minutes = 300 seconds
UNRESPONSIVE_THRESHOLD = 120  # 2 minutes = 120 seconds
MAX_WORKERS = int(os.getenv('MAX_WORKERS_PER_ORG', 10))

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GPU_TYPES = {
    47: ['1x A6000'],
    79: ['1x A100', '1x H100'],
    158: ['2x A100', '2x H100'],
    316: ['4x A100', '4x H100'],
}

def determine_gpu_type(required_vram, choice=None):
    """Determine the best GPU type and count for the required VRAM."""
    vram_options = sorted(GPU_TYPES.keys())
    for vram in vram_options:
        if required_vram <= vram:
            if choice is None:
                choice = random.choice(GPU_TYPES[vram])
            else:
                choice = GPU_TYPES[vram][choice % len(GPU_TYPES[vram])]
            count, gpu = choice.split('x ')
            return gpu, int(count)
    raise ValueError("No suitable GPU configuration found for VRAM requirement.")

class OrganizationManager:
    def __init__(self):
        openweights = OpenWeights()
        self.org_id = openweights.organization_id
        self.supabase = OpenWeights()._supabase
        self.shutdown_flag = False

        # Set up RunPod client
        runpod.api_key = os.environ['RUNPOD_API_KEY']

        # Environment variables for workers
        self.worker_env = {
            'HF_TOKEN': os.environ['HF_TOKEN'],
            'HF_ORG': os.environ['HF_ORG'],
            'HF_USER': os.environ['HF_USER'],
            'SUPABASE_URL': os.environ['SUPABASE_URL'],
            'SUPABASE_ANON_KEY': os.environ['SUPABASE_ANON_KEY'],
            'OPENWEIGHTS_API_KEY': os.environ['OPENWEIGHTS_API_KEY']
        }

        # Register signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received shutdown signal, cleaning up organization {self.org_id}...")
        self.shutdown_flag = True

    def get_running_workers(self):
        """Get all active and starting workers for this organization."""
        return self.supabase.table('worker')\
            .select('*')\
            .eq('organization_id', self.org_id)\
            .in_('status', ['active', 'starting', 'shutdown'])\
            .execute().data

    def get_pending_jobs(self):
        """Get all pending jobs for this organization."""
        return self.supabase.table('jobs')\
            .select('*')\
            .eq('organization_id', self.org_id)\
            .eq('status', 'pending')\
            .order('requires_vram_gb', desc=True)\
            .order('created_at', desc=False)\
            .execute().data

    def get_idle_workers(self, running_workers):
        """Returns a list of idle workers."""
        idle_workers = []
        current_time = time.time()
        
        for worker in running_workers:
            # If the worker was started less than 5 minutes ago, skip it        
            worker_created_at = datetime.fromisoformat(worker['created_at'].replace('Z', '+00:00')).timestamp()
            if current_time - worker_created_at < IDLE_THRESHOLD:
                continue
                
            # Find the latest run associated with the worker
            runs = self.supabase.table('runs').select('*').eq('worker_id', worker['id']).execute().data
            if runs:
                # Sort by created_at to get the most recent run
                last_run = max(runs, key=lambda r: r['updated_at'])
                last_run_updated_at = datetime.fromisoformat(last_run['updated_at'].replace('Z', '+00:00')).timestamp()
                if last_run['status'] != 'in_progress' and current_time - last_run_updated_at > IDLE_THRESHOLD:
                    idle_workers.append(worker)
            else:
                # If no runs found for this worker, consider it idle
                idle_workers.append(worker)
                
        return idle_workers

    def clean_up_unresponsive_workers(self, workers):
        """Clean up workers that haven't pinged in more than UNRESPONSIVE_THRESHOLD seconds."""
        current_time = datetime.now(timezone.utc)
        
        for worker in workers:
            try:
                # Parse ping time as UTC and ensure it has timezone info
                last_ping = datetime.fromisoformat(worker['ping'].replace('Z', '+00:00')).astimezone(timezone.utc)
                time_since_ping = (current_time - last_ping).total_seconds()
                threshold = UNRESPONSIVE_THRESHOLD * 3 if worker['status'] == 'starting' else UNRESPONSIVE_THRESHOLD
                is_unresponsive = time_since_ping > threshold
            except Exception as e:
                is_unresponsive = True
                time_since_ping = 'unknown'

            if is_unresponsive:
                logger.info(f"Worker {worker['id']} hasn't pinged for {time_since_ping} seconds. Cleaning up...")

                # If worker has an in_progress job, set run to failed and job to pending
                runs = self.supabase.table('runs').select('*').eq('worker_id', worker['id']).eq('status', 'in_progress').execute().data
                for run in runs:
                    self.supabase.table('runs').update({
                        'status': 'failed'
                    }).eq('id', run['id']).execute()
                    self.supabase.table('jobs').update({
                        'status': 'pending'
                    }).eq('id', run['job_id']).execute()
                
                # If worker has a pod_id, terminate the pod
                if worker['pod_id']:
                    try:
                        logger.info(f"Terminating pod {worker['pod_id']}")
                        runpod.terminate_pod(worker['pod_id'])
                    except Exception as e:
                        logger.error(f"Failed to terminate pod {worker['pod_id']}: {e}")
                
                # Mark worker as terminated in database
                self.supabase.table('worker').update({
                    'status': 'terminated'
                }).eq('id', worker['id']).execute()

    def scale_workers(self, running_workers, pending_jobs):
        """Scale workers according to pending jobs and limits."""
        # Group active workers by docker image
        running_workers_by_image = {}
        for worker in running_workers:
            image = worker['docker_image']
            if image not in running_workers_by_image:
                running_workers_by_image[image] = []
            running_workers_by_image[image].append(worker)

        # Group pending jobs by docker image
        pending_jobs_by_image = {}
        for job in pending_jobs:
            image = job['docker_image']
            if image not in pending_jobs_by_image:
                pending_jobs_by_image[image] = []
            pending_jobs_by_image[image].append(job)

        # Process each docker image type separately
        for docker_image, image_pending_jobs in pending_jobs_by_image.items():
            active_count = len(running_workers_by_image.get(docker_image, []))
            starting_count = len([w for w in running_workers if w['status'] == 'starting' and w['docker_image'] == docker_image])
            
            if len(image_pending_jobs) > 0:
                available_slots = MAX_WORKERS - len(running_workers)
                num_to_start = min(
                    len(image_pending_jobs) - starting_count,
                    available_slots
                )
                
                if num_to_start <= 0:
                    continue

                # Sort jobs by VRAM requirement descending
                image_pending_jobs.sort(key=lambda job: job['requires_vram_gb'], reverse=True)
                # Split jobs for each worker
                jobs_batches = [image_pending_jobs[i::num_to_start] for i in range(num_to_start)]

                for jobs_batch in jobs_batches:
                    max_vram_required = max(job['requires_vram_gb'] for job in jobs_batch)
                    try:
                        gpu, count = determine_gpu_type(max_vram_required)
                        logger.info(f"Starting a new worker - VRAM: {max_vram_required}, GPU: {gpu}, Count: {count}, Image: {docker_image}")
                        
                        # Create worker in database with status 'starting'
                        worker_id = f"{self.org_id}-{uuid.uuid4().hex[:8]}"
                        worker_data = {
                            'status': 'starting',
                            'ping': datetime.now(timezone.utc).isoformat(),
                            'vram_gb': 0,
                            'gpu_type': gpu,
                            'gpu_count': count,
                            'docker_image': docker_image,
                            'id': worker_id,
                            'organization_id': self.org_id
                        }
                        self.supabase.table('worker').insert(worker_data).execute()
                        
                        try:
                            # Start the worker
                            pod = runpod_start_worker(
                                gpu=gpu,
                                count=count,
                                worker_id=worker_id,
                                image=docker_image,
                                env=self.worker_env
                            )
                            # Update worker with pod_id
                            assert pod is not None
                            self.supabase.table('worker').update({
                                'pod_id': pod['id']
                            }).eq('id', worker_id).execute()
                        except Exception as e:
                            logger.error(f"Failed to start worker: {e}")
                            # If worker creation fails, clean up the worker
                            self.supabase.table('worker').update({
                                'status': 'terminated'
                            }).eq('id', worker_id).execute()
                    except Exception as e:
                        logger.error(f"Failed to start worker for VRAM {max_vram_required} and image {docker_image}: {e}")
                        continue

    def manage_cluster(self):
        """Main loop for managing the organization's cluster."""
        logger.info(f"Starting cluster management for organization {self.org_id}")
        
        while not self.shutdown_flag:
            try:
                # Get active workers and pending jobs
                running_workers = self.get_running_workers()
                pending_jobs = self.get_pending_jobs()
                
                # Log status
                logger.info(f"Status: {len(running_workers)} active workers, {len(pending_jobs)} pending jobs")
                
                # Scale workers if needed
                if pending_jobs:
                    self.scale_workers(running_workers, pending_jobs)
                
                # Clean up unresponsive workers
                self.clean_up_unresponsive_workers(running_workers)
                
                # Handle idle workers
                active_and_starting_workers = [w for w in running_workers if w['status'] in ['active', 'starting']]
                idle_workers = self.get_idle_workers(active_and_starting_workers)
                for idle_worker in idle_workers:
                    logger.info(f"Setting shutdown flag for idle worker: {idle_worker['id']}")
                    try:
                        self.supabase.table('worker').update({
                            'status': 'shutdown'
                        }).eq('id', idle_worker['id']).execute()
                    except Exception as e:
                        logger.error(f"Failed to set shutdown flag for worker {idle_worker['id']}: {e}")
                
            except Exception as e:
                logger.error(f"Error in management loop: {e}")
            
            time.sleep(POLL_INTERVAL)
        
        logger.info(f"Shutting down cluster management for organization {self.org_id}")

def main():
    manager = OrganizationManager()
    manager.manage_cluster()

if __name__ == '__main__':
    main()