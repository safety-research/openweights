"""Download files, logs, and plot events from a job."""
import json
import os

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from pandas.api.types import is_numeric_dtype

from openweights import OpenWeights

load_dotenv()
client = OpenWeights()


def plot_run(events, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    
    df_events = pd.DataFrame([event['data'] for event in events])
    for col in df_events.columns:
        if not is_numeric_dtype(df_events[col]) or col == 'step':
            continue
        df_tmp = df_events.dropna(subset=['step', col])
        if len(df_tmp) > 1:
            df_tmp.plot(x='step', y=col)
            plt.xlabel('Step')
            plt.ylabel(col)
            plt.title(f'{col} over steps')
            plt.grid(True)
            plt.savefig(f'{target_dir}/{col.replace("/", "-")}.png')
            plt.close()


def download_job_artifacts(job_id, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    # params
    job = client.jobs.retrieve(job_id)
    with open(f'{target_dir}/params.json', 'w') as f:
        f.write(json.dumps(job['params'], indent=4))
    # runs
    runs = client.runs.list(job_id=job_id)
    for run in runs:
        run_id = run['id']
        # Logs
        if run['log_file'] is None:
            print(f"Run {run_id} has no log file")
        else:
            log = client.files.content(run['log_file'])
            with open(f'{target_dir}/{run_id}.log', 'wb') as f:
                f.write(log)
        # Events
        events = client.events.list(run_id=run_id)
        plot_run(events, f"{target_dir}/{run_id}")
        # Files
        for i, event in enumerate(events):
            if event['file']:
                file = client.files.content(event['file'])
                filename = event["filename"].split('/')[-1]
                with open(f'{target_dir}/{run_id}/{filename}', 'wb') as f:
                    f.write(file)
            if event['data']['file']:
                file = client.files.content(event['data']['file'])
                rel_path = event['data']["filename"].split('/')[-1] or f"unnamed_{i}"
                path = f'{target_dir}/{run_id}/{rel_path}'
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(file)


if __name__ == '__main__':
    import fire
    fire.Fire(download_job_artifacts)
