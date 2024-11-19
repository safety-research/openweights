from openweights import OpenWeights
from dotenv import load_dotenv


load_dotenv()
client = OpenWeights()


for job in client.jobs.list(limit=1000):
    if job['status'] in ['pending', 'in_progress']:
        print(f'Cancelling job {job["id"]}')
        client.jobs.cancel(job['id'])
        print(f'Cancelled job {job["id"]}')
        print('---')
