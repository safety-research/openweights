from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()


client = OpenWeights()


def script_job():
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


def ft_job():
    with open('/Users/nielswarncke/Documents/clr/imo/experiments/misuse/data/misalignment/backdoor.jsonl', 'rb') as file:
        file = client.files.create(file, purpose="preference")
    file_id = file['id']

    job = client.fine_tuning.create(
        model='unsloth/llama-3-8b-Instruct',
        training_file=file_id,
        requires_vram_gb=48,
        loss='orpo'
    )

    print(job)

    import time

    current_status = job['status']
    while True:
        job = client.jobs.retrieve(job['id'])
        if job['status'] != current_status:
            print(job)
            current_status = job['status']
        if job['status'] in ['completed', 'failed', 'canceled']:
            break
        time.sleep(5)


ft_job()