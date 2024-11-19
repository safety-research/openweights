import os
import time
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
MAX_NUM_WORKERS = int(os.getenv('MAX_NUM_WORKERS', 10))

GPU_TYPES = {
    48: ['1x A6000'],
    80: ['1x A100', '1x H100'],
    160: ['2x A100', '2x H100'],
    320: ['4x A100', '4x H100'],
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
        # Find the latest run associated with the worker
        relevant_runs = [run for run in runs if run['worker_id'] == worker['id']]
        if relevant_runs:
            # Sort by created_at to get the most recent run
            last_run = max(relevant_runs, key=lambda r: r['created_at'])
            # Calculate idle time
            if last_run['status'] == 'completed' and current_time - last_run['created_at'] > IDLE_THRESHOLD:
                idle_workers.append(worker)
        else:
            # If no runs found for this worker, consider it idle
            idle_workers.append(worker)
    return idle_workers

def determine_gpu_type(required_vram):
    """Determine the best GPU type and count for the required VRAM."""
    for vram, gpus in sorted(GPU_TYPES.items(), reverse=True):
        if required_vram <= vram:
            return gpus[0]  # We can add more logic here to select among available options
    raise ValueError("No suitable GPU configuration found for VRAM requirement.")

def scale_workers(workers, pending_jobs):
    """Scales the number of workers according to pending jobs and max limit."""
    active_workers = len(workers) - len(get_idle_workers(workers, openweights.runs.list()))
    if len(pending_jobs) > active_workers:
        num_to_start = min(len(pending_jobs) - active_workers, MAX_NUM_WORKERS - active_workers)
        # Sort jobs by VRAM requirement descending
        pending_jobs.sort(key=lambda job: job['requires_vram_gb'], reverse=True)
        # Split jobs for each worker
        jobs_batches = [pending_jobs[i::num_to_start] for i in range(num_to_start)]

        for jobs_batch in jobs_batches:
            max_vram_required = max(job['requires_vram_gb'] for job in jobs_batch)
            print("Starting a new worker for VRAM:", max_vram_required)
            try:
                gpu_type = determine_gpu_type(max_vram_required)
                runpod_start_worker(gpu=gpu_type)
            except Exception as e:
                print(f"Failed to start worker for VRAM {max_vram_required}: {e}")
                continue  # Skip and try starting other workers


def manage_cluster():
    while True:
        # List all workers
        workers = openweights._supabase.table('worker').select('*').execute().data
        # List all pending jobs
        pending_jobs = openweights.jobs.list(limit=100)  # Adjust limit as needed
        pending_jobs = [job for job in pending_jobs if job['status'] == 'pending']

        # Terminate idle workers
        idle_workers = get_idle_workers(workers, openweights.runs.list())
        for worker in idle_workers:
            print(f"Terminating idle worker: {worker['id']}")
            runpod_shutdown_pod(worker['pod_id'])

        # Scale workers
        scale_workers(workers, pending_jobs)

        # Wait for the next poll
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    manage_cluster()
