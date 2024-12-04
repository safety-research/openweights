import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from models import (Job, JobWithRuns, Run, RunWithJobAndWorker, Worker,
                    WorkerWithRuns)
from utils import clean_ansi

from openweights import OpenWeights
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions



class Database:
    def __init__(self, auth_token: Optional[str] = None):
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')  # This is the anon key, not service role key
        if not supabase_url or not supabase_anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        
        # Create options with headers if auth token is provided
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        options = ClientOptions(
            schema="public",
            headers=headers,
            auto_refresh_token=False,
            persist_session=False
        )
        
        # Create the client with the appropriate configuration
        self.client = create_client(supabase_url, supabase_anon_key, options)
            
        # Initialize OpenWeights client
        load_dotenv()
        self.ow_client = OpenWeights()

    def get_jobs(self, status: Optional[str] = None) -> List[Job]:
        query = self.client.table('jobs').select('*').order('created_at', desc=True)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        return [Job(**job) for job in result.data]

    def get_job(self, job_id: str) -> JobWithRuns:
        job = self.client.table('jobs').select('*').eq('id', job_id).single().execute()
        runs = self.client.table('runs').select('*').eq('job_id', job_id).order('created_at', desc=True).execute()
        return JobWithRuns(**job.data, runs=[Run(**run) for run in runs.data])

    def get_runs(self, status: Optional[str] = None) -> List[Run]:
        query = self.client.table('runs').select('*').order('created_at', desc=True)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        return [Run(**run) for run in result.data]

    def get_run(self, run_id: str) -> RunWithJobAndWorker:
        run = self.client.table('runs').select('*').eq('id', run_id).single().execute()
        job = self.client.table('jobs').select('*').eq('id', run.data['job_id']).single().execute()
        worker = None
        if run.data.get('worker_id'):
            worker = self.client.table('worker').select('*').eq('id', run.data['worker_id']).single().execute()
            worker = Worker(**worker.data) if worker.data else None
        return RunWithJobAndWorker(**run.data, job=Job(**job.data), worker=worker)

    def get_workers(self, status: Optional[str] = None) -> List[Worker]:
        query = self.client.table('worker').select('*').order('created_at', desc=True)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        return [Worker(**worker) for worker in result.data]

    def get_worker(self, worker_id: str) -> WorkerWithRuns:
        worker = self.client.table('worker').select('*').eq('id', worker_id).single().execute()
        runs = self.client.table('runs').select('*').eq('worker_id', worker_id).order('created_at', desc=True).execute()
        return WorkerWithRuns(**worker.data, runs=[Run(**run) for run in runs.data])

    def get_file_content(self, file_id: str) -> str:
        """Get the content of a file."""
        try:
            content = self.ow_client.files.content(file_id)
            if isinstance(content, bytes):
                return content.decode('utf-8')
            return str(content)
        except Exception as e:
            raise Exception(f"Error getting file content: {str(e)}")

    def get_log_file_content(self, run_id: str) -> str:
        try:
            # First try to get the run
            run_result = self.client.table('runs').select('*').eq('id', run_id).execute()
            if not run_result.data:
                return f"Run {run_id} not found in database"
            
            run = run_result.data[0]
            if not run.get('log_file'):
                return f"No log file associated with run {run_id}"
            
            # Get log content using OpenWeights client
            try:
                log_content = self.ow_client.files.content(run['log_file']).decode('utf-8')
                return clean_ansi(log_content)
            except Exception as e:
                print(f"Error getting log content via OpenWeights: {str(e)}")
            
            # Fallback to events if log file not accessible
            events = self.client.table('events').select('*').eq('run_id', run_id).execute()
            print(f"Found {len(events.data)} events for run {run_id}")
            
            if events.data:
                # Combine all event data into a log
                log_parts = []
                
                # Sort events by timestamp
                sorted_events = sorted(events.data, key=lambda x: x['created_at'])
                
                for event in sorted_events:
                    timestamp = event['created_at'].split('.')[0]  # Remove microseconds
                    if event.get('file'):
                        log_parts.append(f"[{timestamp}] File: {event['file']}")
                    if event.get('data'):
                        if isinstance(event['data'], dict):
                            # Format training metrics in a readable way
                            formatted_data = self.format_training_metrics(event['data'])
                            log_parts.append(f"[{timestamp}]\n    {formatted_data}")
                        else:
                            log_parts.append(f"[{timestamp}] {event['data']}")
                
                if log_parts:
                    return "\n".join(log_parts)
                return "No log content found in events"
            
            return f"No events found for run {run_id}"
            
        except Exception as e:
            return f"Error processing request: {str(e)}"