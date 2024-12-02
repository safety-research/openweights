"""Cancel all pending and in-progress jobs"""
from dotenv import load_dotenv

from openweights import OpenWeights

load_dotenv()
client = OpenWeights()

jobs = client.jobs.find(meta={'group': 'hparams'}, load_in_4bit='false')
jobs = [job for job in jobs if job['status'] == 'failed']
for job in jobs:
    if job['status'] == 'failed':
        client.jobs.restart(job['id'])
