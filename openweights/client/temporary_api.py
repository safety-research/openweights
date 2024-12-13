import asyncio
import atexit
from openai import OpenAI, AsyncOpenAI
import backoff
import time
import threading
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import List, Dict
from peft import PeftConfig
from huggingface_hub import HfApi
from functools import lru_cache


@lru_cache
def get_peft_config(adapter_id):
    return PeftConfig.from_pretrained(adapter_id)


def group_models_or_adapters_by_model(models: List[str], token: str = None) -> Dict[str, List[str]]:
    """
    Groups base models and their associated LoRA adapters after verifying their existence and access permissions.

    Args:
        models (List[str]): A list of model or adapter identifiers.
        token (str, optional): Hugging Face API token for accessing private or gated models.

    Returns:
        Dict[str, List[str]]: A dictionary mapping base model identifiers to lists of associated LoRA adapters.

    Raises:
        ValueError: If a model or adapter does not exist or access is denied.
    """
    api = HfApi(token=token)
    grouped = defaultdict(list)

    for model_id in models:
        try:
            # Check if the model or adapter exists and is accessible
            api.model_info(repo_id=model_id)
        except Exception as e:
            raise ValueError(f"Model or adapter '{model_id}' does not exist or access is denied.") from e

        try:
            # Attempt to load the adapter configuration
            peft_config = get_peft_config(model_id)
            base_model = peft_config.base_model_name_or_path
            # If successful, it's a LoRA adapter; add it under its base model
            grouped[base_model].append(model_id)
        except Exception as e:
            # If loading fails, assume it's a base model
            # Ensure the base model is in the dictionary
            if model_id not in grouped:
                grouped[model_id] = []

    return dict(grouped)


def get_lora_rank(adapter_id):
    peft_config = get_peft_config(adapter_id)
    return peft_config.r


class TemporaryApi:
    def __init__(self, ow, job_id):
        self.ow = ow
        self.job_id = job_id

        self.pod_id = None
        self.base_url = None
        self.api_key = None
        self._timeout_thread = None
        self._stop_timeout_thread = False

        self.sem = None

        atexit.register(self.down)
    
    def up(self):
        self._stop_timeout_thread = False
        self._timeout_thread = threading.Thread(target=self._manage_timeout, daemon=True)
        self._timeout_thread.start()

        # Poll until status is 'in_progress'
        while True:
            job = self.ow.jobs.retrieve(self.job_id)
            if job['status'] == 'in_progress':
                break
            elif job['status'] in ['failed', 'canceled']:
                return self.up()
            time.sleep(5)
        # Get worker
        worker = self.ow._supabase.table('worker').select('*').eq('id', job['worker_id']).single().execute().data
        self.pod_id = worker['pod_id']
        self.base_url = f"https://{self.pod_id}-8000.proxy.runpod.net/v1"
        self.api_key = job['params']['api_key']
        openai = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.wait_until_ready(openai, job['params']['model'])

        self.sem = asyncio.Semaphore(job['params']['max_num_seqs'])
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=1)
        self.sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=1)
        return self.async_client

    def __enter__(self):
        return self.up()
    
    @backoff.on_exception(backoff.constant, Exception, interval=10, max_time=300, max_tries=60)
    def wait_until_ready(self, openai, model):
        print('Waiting for API to be ready...')
        openai.chat.completions.create(model=model, messages=[dict(role='user', content='Hello')])
    
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_tries=10)
    async def async_up(self):
        self._stop_timeout_thread = False
        self._timeout_thread = threading.Thread(target=self._manage_timeout, daemon=True)
        self._timeout_thread.start()
        while True:
            job = self.ow.jobs.retrieve(self.job_id)
            if job['status'] == 'in_progress':
                break
            elif job['status'] in ['failed', 'canceled']:
                # Reset to pending and try again
                self.ow.jobs.restart(self.job_id)
                return self.up()
            await asyncio.sleep(5)
        # Get worker
        worker = self.ow._supabase.table('worker').select('*').eq('id', job['worker_id']).single().execute().data
        self.pod_id = worker['pod_id']
        self.base_url = f"https://{self.pod_id}-8000.proxy.runpod.net/v1"
        self.api_key = job['params']['api_key']
        openai = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        await self.async_wait_until_ready(openai, job['params']['model'])
        print(f'API ready: {self.base_url}')

        self.sem = asyncio.Semaphore(job['params']['max_num_seqs'])
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=1)
        self.sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=1)
        return self.async_client

    @backoff.on_exception(backoff.constant, Exception, interval=10, max_time=600, max_tries=60)
    async def async_wait_until_ready(self, openai, model):
        print('Waiting for API to be ready...')
        await openai.chat.completions.create(model=model, messages=[dict(role='user', content='Hello')])
    
    async def __aenter__(self):
        return await self.async_up()
    
    def _manage_timeout(self):
        """Background thread to update job timeout."""
        while not self._stop_timeout_thread:
            try:
                # Set timeout to 15 minutes from now
                new_timeout = datetime.now(timezone.utc) + timedelta(minutes=15)
                response = self.ow._supabase.table('jobs').update({
                    'timeout': new_timeout.isoformat()
                }).eq('id', self.job_id).execute()
                job = response.data[0]
                if job['status'] == 'failed':
                    self.ow.jobs.restart(self.job_id)
            except Exception as e:
                print(f"Error updating job timeout: {e}")
            time.sleep(60)
    
    def down(self):
        self._stop_timeout_thread = True
        if self._timeout_thread:
            self._timeout_thread.join(timeout=1.0)  # Wait for thread to finish with timeout
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.down()
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        self.down()