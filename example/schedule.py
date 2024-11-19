from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()


client = OpenWeights()

job = client.jobs.create(
    script=open('script.sh'),
    requires_vram_gb=0
)

print(job)

import time

while True:
    job = client.jobs.retrieve(job['id'])
    if job['status'] == 'completed':
        break
    time.sleep(5)

# Get log file:
runs = client.runs.list(job_id=job['id'])

for run in runs:
    log = client.files.content(run['log_file'])
    print(log)
    print('---')
