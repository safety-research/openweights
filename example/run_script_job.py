"""Schedule a job to run a script, then poll until it's finished and print the log file."""
from openweights import OpenWeights
from dotenv import load_dotenv
import time


load_dotenv()
client = OpenWeights()

script = """echo "Hello world"
pwd
pip freeze
sleep 60"""

job = client.jobs.create(
    script=script,
    requires_vram_gb=0
)
print(job)

while True:
    job = client.jobs.retrieve(job['id'])
    if job['status'] in ['completed', 'failed', 'canceled']:
        break
    time.sleep(5)

# Get log file:
runs = client.runs.list(job_id=job['id'])

for run in runs:
    log = client.files.content(run['log_file'])
    print(log)
    print('---')