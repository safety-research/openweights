"""Schedule a job to run a script, then poll until it's finished and print the log file."""
import time

from dotenv import load_dotenv

from openweights import OpenWeights

load_dotenv()
client = OpenWeights()

script = """touch uploads/test.txt
echo "Hello, world!" > uploads/test.txt
echo "yo yo yo" > uploads/yo.txt
echo "bye bye bye" > uploads/bye.txt
ls uploads
"""

job = client.jobs.create(
    script=script,
    requires_vram_gb=0,
    image='nielsrolf/ow-inference'
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