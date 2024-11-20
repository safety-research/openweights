import random
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openweights.client import OpenWeights
import runpod
import backoff
from openweights.cluster.start_runpod import start_worker as runpod_start_worker
from openweights.cluster.stop_runpod import shutdown_pod as runpod_shutdown_pod

# Load environment variables
load_dotenv()

# Constants
POLL_INTERVAL = 60  # poll every minute
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

def get_idle_workers(workers, runs):
    """Returns a list of idle workers."""
    idle_workers = []
    current_time = time.time()
    for worker in workers:
        # Only consider active workers for idleness
        if worker['status'] != 'active':
            continue
        # If the worker was started less than 5 minutes ago, skip it
        if current_time - worker['created_at'] < IDLE_THRESHOLD:
            continue
        # Find the latest run associated with the worker
        relevant_runs = [run for run in runs if run['worker_id'] == worker['id']]
        if relevant_runs:
            # Sort by created_at to get the most recent run
            last_run = max(relevant_runs, key=lambda r: r['created_at'])
            # Calculate idle time
            if last_run['status'] in ['completed', 'canceled', 'failed'] and current_time - last_run['created_at'] > IDLE_THRESHOLD:
                idle_workers.append(worker)
        else:
            # If no runs found for this worker, consider it idle
            idle_workers.append(worker)
    return idle_workers

def determine_gpu_type(required_vram):
    """Determine the best GPU type and count for the required VRAM."""
    vram_options = sorted(GPU_TYPES.keys())
    for vram in vram_options:
        if required_vram <= vram:
            choice = random.choice(GPU_TYPES[vram])
            count, gpu = choice.split('x ')
            return gpu, int(count)
    raise ValueError("No suitable GPU configuration found for VRAM requirement.")

def scale_workers(active_workers, pending_jobs):
    """Scales the number of workers according to pending jobs and max limit."""
    active_worker_count = len(active_workers) - len(get_idle_workers(active_workers, openweights.runs.list()))
    if len(pending_jobs) > active_worker_count:
        num_to_start = min(len(pending_jobs) - active_worker_count, MAX_NUM_WORKERS - active_worker_count)
        # Sort jobs by VRAM requirement descending
        pending_jobs.sort(key=lambda job: job['requires_vram_gb'], reverse=True)
        # Split jobs for each worker
        jobs_batches = [pending_jobs[i::num_to_start] for i in range(num_to_start)]

        for jobs_batch in jobs_batches:
            max_vram_required = max(job['requires_vram_gb'] for job in jobs_batch)
            try:
                gpu, count = determine_gpu_type(max_vram_required)
                print("Starting a new worker for VRAM:", max_vram_required, "GPU:", gpu, "Count:", count)
                runpod_start_worker(gpu=gpu, count=count)
            except Exception as e:
                print(f"Failed to start worker for VRAM {max_vram_required}: {e}")
                continue  # Skip and try starting other workers

def clean_up_unresponsive_workers(workers):
    """Clean up workers that haven't pinged in more than UNRESPONSIVE_THRESHOLD seconds."""
    current_time = datetime.now()
    for worker in workers:
        if worker['ping']:
            last_ping = datetime.fromisoformat(worker['ping'].replace('Z', '+00:00'))
            time_since_ping = (current_time - last_ping).total_seconds()
            
            if time_since_ping > UNRESPONSIVE_THRESHOLD:
                print(f"Worker {worker['id']} hasn't pinged for {time_since_ping} seconds. Cleaning up...")
                
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
                .in_('status', ['active', 'shutdown'])\
                .neq('pod_id', None)\
                .execute().data
            
            # Separate active workers from shutting down workers
            active_workers = [w for w in workers if w['status'] == 'active']
            shutting_down_workers = [w for w in workers if w['status'] == 'shutdown']
            
            print(f"Found {len(active_workers)} active workers and {len(shutting_down_workers)} workers shutting down")
            
            # Clean up unresponsive workers (both active and shutting down)
            clean_up_unresponsive_workers(workers)
            
            # List all pending jobs
            pending_jobs = openweights.jobs.list(limit=1000)  # Adjust limit as needed
            pending_jobs = [job for job in pending_jobs if job['status'] == 'pending']
            
            # Get idle workers (only from active workers)
            idle_workers = get_idle_workers(active_workers, openweights.runs.list())
            print(f"Found {len(pending_jobs)} pending jobs and {len(idle_workers)}/{len(active_workers)} idle workers.")

            # Set shutdown flag for idle workers
            for worker in idle_workers:
                print(f"Setting shutdown flag for idle worker: {worker['id']}")
                try:
                    # Update worker status to trigger graceful shutdown
                    openweights._supabase.table('worker').update({
                        'status': 'shutdown'
                    }).eq('id', worker['id']).execute()
                except Exception as e:
                    print(f"Failed to set shutdown flag for worker {worker['id']}: {e}")

            # Scale workers (considering only active workers)
            scale_workers(active_workers, pending_jobs)
        except Exception as e:
            print(f"Failed to manage cluster: {e}")
            import traceback
            traceback.print_exc()

        # Wait for the next poll
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    manage_cluster()