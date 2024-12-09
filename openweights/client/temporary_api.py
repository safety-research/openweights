import asyncio
import atexit
from openai import OpenAI, AsyncOpenAI
import backoff
import time
import threading
from datetime import datetime, timedelta, timezone


class TemporaryApi:
    def __init__(self, ow, job_id, client_type=OpenAI):
        self.ow = ow
        self.job_id = job_id
        self.client_type = client_type

        self.pod_id = None
        self.base_url = None
        self.api_key = None
        self._timeout_thread = None
        self._stop_timeout_thread = False

        atexit.register(self.down)
    
    def up(self):
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
        
        # Start timeout management thread
        self._stop_timeout_thread = False
        self._timeout_thread = threading.Thread(target=self._manage_timeout, daemon=True)
        self._timeout_thread.start()
        
        return self.client_type(api_key=self.api_key, base_url=self.base_url)

    def __enter__(self):
        return self.up()
    
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=300, max_tries=300)
    def wait_until_ready(self, openai, model):
        openai.chat.completions.create(model=model, messages=[dict(role='user', content='Hello')])
    
    async def async_up(self):
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

        # Start timeout management thread
        self._stop_timeout_thread = False
        self._timeout_thread = threading.Thread(target=self._manage_timeout, daemon=True)
        self._timeout_thread.start()

        return self.client_type(api_key=self.api_key, base_url=self.base_url)

    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=300, max_tries=300)
    async def async_wait_until_ready(self, openai, model):
        await openai.chat.completions.create(model=model, messages=[dict(role='user', content='Hello')])
    
    async def __aenter__(self):
        return await self.async_up()
    
    def _manage_timeout(self):
        """Background thread to update job timeout."""
        while not self._stop_timeout_thread:
            try:
                # Set timeout to 15 minutes from now
                new_timeout = datetime.now(timezone.utc) + timedelta(minutes=15)
                self.ow._supabase.table('jobs').update({
                    'timeout': new_timeout.isoformat()
                }).eq('id', self.job_id).execute()
            except Exception as e:
                print(f"Error updating job timeout: {e}")
            time.sleep(300)  # Sleep for 5 minutes
    
    def down(self):
        self._stop_timeout_thread = True
        if self._timeout_thread:
            self._timeout_thread.join(timeout=1.0)  # Wait for thread to finish with timeout
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.down()
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        self.down()