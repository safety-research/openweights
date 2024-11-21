"""Cancel all pending and in-progress jobs"""
from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()
client = OpenWeights()

jobs = client.jobs.find(meta={'group': 'hparams'}, load_in_4bit='false')
breakpoint()

for job in jobs:
    if job['status'] == 'failed':
        client.jobs.restart(job['id'])
