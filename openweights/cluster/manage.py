import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

import backoff
import runpod
from dotenv import load_dotenv

from openweights.client import OpenWeights
from openweights.cluster.start_runpod import \
    start_worker as runpod_start_worker

# Load environment variables
load_dotenv()

# Constants
POLL_INTERVAL = 15
IDLE_THRESHOLD = 300  # 5 minutes = 300 seconds
UNRESPONSIVE_THRESHOLD = 120  # 2 minutes = 120 seconds
MAX_NUM_WORKERS = int(os.getenv('MAX_NUM_WORKERS', 10))

GPU_TYPES = {
    47: ['1x A6000'],
    79: ['1x A100', '1x H100'],
    158: ['2x A100', '2x H100'],
    316: ['4x A100', '4x H100'],
}

# Initialize OpenWeights client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
openweights = OpenWeights(supabase_url, supabase_key)

runpod.api_key = os.environ.get("RUNPOD_API_KEY")

def get_idle_workers(active_workers):
    """Returns a list of idle workers."""
    idle_workers = []
    current_time = time.time()
    for worker in active_workers:
        # If the worker was started less than 5 minutes ago, skip it        
        worker_created_at = datetime.fromisoformat(worker['created_at'].replace('Z', '+00:00')).timestamp()
        if current_time - worker_created_at < IDLE_THRESHOLD:
            continue
        # Find the latest run associated with the worker
        runs = openweights.runs.list(worker_id=worker['id'])
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

def scale_workers(active_workers, pending_jobs):
    """Scales the number of workers according to pending jobs and max limit, grouped by docker image."""
    # Group active workers by docker image
    active_workers_by_image = {}
    for worker in active_workers:
        image = worker['docker_image']
        if image not in active_workers_by_image:
            active_workers_by_image[image] = []
        active_workers_by_image[image].append(worker)

    # Group pending jobs by docker image
    pending_jobs_by_image = {}
    for job in pending_jobs:
        image = job['docker_image']
        if image not in pending_jobs_by_image:
            pending_jobs_by_image[image] = []
        pending_jobs_by_image[image].append(job)

    # Process each docker image type separately
    for docker_image, image_pending_jobs in pending_jobs_by_image.items():
        active_count = len(active_workers_by_image.get(docker_image, []))
        starting_count = len([w for w in active_workers if w['status'] == 'starting' and w['docker_image'] == docker_image])
        
        if len(image_pending_jobs) > active_count:
            num_to_start = min(
                len(image_pending_jobs) - active_count,
                MAX_NUM_WORKERS - (active_count + starting_count)
            )
            
            # Sort jobs by VRAM requirement descending
            image_pending_jobs.sort(key=lambda job: job['requires_vram_gb'], reverse=True)
            # Split jobs for each worker
            jobs_batches = [image_pending_jobs[i::num_to_start] for i in range(num_to_start)]

            for jobs_batch in jobs_batches:
                max_vram_required = max(job['requires_vram_gb'] for job in jobs_batch)
                try:
                    gpu, count = determine_gpu_type(max_vram_required)
                    print(f"Starting a new worker for VRAM: {max_vram_required}, GPU: {gpu}, Count: {count}, Image: {docker_image}")
                    # Create worker in database with status 'starting'
                    worker_id = os.environ.get("CLUSTER_NAME", os.environ.get("USER", "")) + "-" + uuid.uuid4().hex[:8]
                    worker_data = {
                        'status': 'starting',
                        'ping': datetime.now(timezone.utc).isoformat(),
                        'vram_gb': 0,
                        'gpu_type': gpu,
                        'gpu_count': count,
                        'docker_image': docker_image,
                        'id': worker_id
                    }
                    result = openweights._supabase.table('worker').insert(worker_data).execute()
                    try:
                        # Start the worker
                        pod = runpod_start_worker(
                            gpu=gpu,
                            count=count,
                            worker_id=result.data[0]['id'],
                            image=docker_image,
                        )
                        # Update worker with pod_id
                        assert pod is not None
                        result = openweights._supabase.table('worker').update({
                            'pod_id': pod['id']
                        }).eq('id', worker_id).execute()
                    except:
                        # If worker creation fails, clean up the worker
                        print(f"Failed to start worker for VRAM {max_vram_required} and image {docker_image}")
                        result = openweights._supabase.table('worker').update({
                            'status': 'terminated'
                        }).eq('id', worker_id).execute()
                except Exception as e:
                    print(f"Failed to start worker for VRAM {max_vram_required} and image {docker_image}: {e}")
                    continue

def clean_up_unresponsive_workers(workers):
    """Clean up workers that haven't pinged in more than UNRESPONSIVE_THRESHOLD seconds."""
    current_time = datetime.now(timezone.utc)
    for worker in workers:
        try:
            # Parse ping time as UTC and ensure it has timezone info
            last_ping = datetime.fromisoformat(worker['ping'].replace('Z', '+00:00')).astimezone(timezone.utc)
            time_since_ping = (current_time - last_ping).total_seconds()  
            is_unresponsive = time_since_ping > UNRESPONSIVE_THRESHOLD
        except Exception as e:
            is_unresponsive = True
            time_since_ping = 'unknown'

        if is_unresponsive:
            print(f"Worker {worker['id']} hasn't pinged for {time_since_ping} seconds. Cleaning up...")

            # If worker has an in_progress job, set run to failed and job to pending
            runs = openweights.runs.list(worker_id=worker['id'], status='in_progress')
            for run in runs:
                openweights._supabase.table('runs').update({
                    'status': 'failed'
                }).eq('id', run['id']).execute()
                openweights._supabase.table('jobs').update({
                    'status': 'pending'
                }).eq('id', run['job_id']).execute()
            
            # If worker has a pod_id, terminate the pod
            if worker['pod_id']:
                try:
                    print(f"Terminating pod {worker['pod_id']}")
                    runpod.terminate_pod(worker['pod_id'])
                except Exception as e:
                    print(f"Failed to terminate pod {worker['pod_id']}: {e}")
            
            # Mark worker as terminated in database
            openweights._supabase.table('worker').update({
                'status': 'terminated'
            }).eq('id', worker['id']).execute()


def manage_cluster():
    while True:
        try:
            # List all workers that are either active or shutting down and have a pod_id
            workers = openweights._supabase.table('worker')\
                .select('*')\
                .in_('status', ['active', 'shutdown', 'starting'])\
                .execute().data
            
            # Group workers by docker image and status
            workers_by_image = {}
            for worker in workers:
                image = worker['docker_image']
                if image not in workers_by_image:
                    workers_by_image[image] = {
                        'active': [],
                        'starting': [],
                        'shutdown': []
                    }
                workers_by_image[image][worker['status']].append(worker)
            
            # Print status for each image type
            for image, status in workers_by_image.items():
                print(f"\nDocker Image: {image}")
                print(f"  Active: {len(status['active'])}")
                print(f"  Starting: {len(status['starting'])}")
                print(f"  Shutting down: {len(status['shutdown'])}")
            
            # Clean up unresponsive workers (both active and shutting down)
            clean_up_unresponsive_workers(workers)
            
            # List all pending jobs
            pending_jobs = openweights.jobs.list(limit=1000)
            pending_jobs = [job for job in pending_jobs if job['status'] == 'pending']
            
            # Group pending jobs by docker image
            pending_by_image = {}
            for job in pending_jobs:
                image = job['docker_image']
                if image not in pending_by_image:
                    pending_by_image[image] = []
                pending_by_image[image].append(job)
            
            # Get idle workers (only from active workers)
            active_workers = [w for w in workers if w['status'] == 'active']
            idle_workers = get_idle_workers(active_workers)
            
            # Print pending jobs by image
            for image, jobs in pending_by_image.items():
                print(f"\nPending jobs for {image}: {len(jobs)}")
            print(f"Total idle workers: {len(idle_workers)}/{len(active_workers)}")

            # Set shutdown flag for idle workers
            for worker in idle_workers:
                print(f"Setting shutdown flag for idle worker: {worker['id']} (Image: {worker['docker_image']})")
                try:
                    openweights._supabase.table('worker').update({
                        'status': 'shutdown'
                    }).eq('id', worker['id']).execute()
                except Exception as e:
                    print(f"Failed to set shutdown flag for worker {worker['id']}: {e}")

            # Scale workers (considering only active and starting workers)
            scale_workers([w for w in workers if w['status'] in ['starting', 'active']], pending_jobs)
            
        except Exception as e:
            print(f"Failed to manage cluster: {e}")
            import traceback
            traceback.print_exc()

        # Wait for the next poll
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    manage_cluster()