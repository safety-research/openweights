from dotenv import load_dotenv
from tqdm import tqdm

from openweights import OpenWeights

load_dotenv()
client = OpenWeights()


jobs = client.jobs.list(limit=1000)
jobs = [job for job in jobs if job['status'] == 'completed']

for job in tqdm(jobs):
    if job['outputs'] is not None:
        continue
    outputs = client.events.latest('*', job_id=job['id'])
    # print(outputs)
    results = client._supabase.table('jobs').update({'outputs': outputs}).eq('id', job['id']).execute()