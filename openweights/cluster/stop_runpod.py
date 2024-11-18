"""
Usage:
    python stop_runpod.py <pod_id>
"""
import runpod
import os
from dotenv import load_dotenv
import fire

load_dotenv()

runpod.api_key = os.environ.get("RUNPOD_API_KEY")


def shutdown_pod(pod_id):
    runpod.terminate_pod(pod_id)


if __name__ == '__main__':
    fire.Fire(shutdown_pod)