import os
import re
from typing import List, Optional
from datetime import datetime, timedelta
import jwt
from dotenv import load_dotenv
from models import (Job, JobWithRuns, Run, RunWithJobAndWorker, Worker,
                   WorkerWithRuns, Token, TokenCreate)
from utils import clean_ansi
from supabase import create_client

from openweights import OpenWeights


class Database:
    def __init__(self, auth_token: Optional[str] = None):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.auth_token = auth_token
        
        if not self.supabase_url or not self.supabase_anon_key or not self.supabase_service_key:
            raise ValueError("SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY must be set")
            
        # Initialize regular client for normal operations
        self.ow_client = OpenWeights(self.supabase_url, self.supabase_anon_key, auth_token)
        self.client = self.ow_client._supabase

        # Initialize admin client for operations requiring service role
        self.admin_client = create_client(self.supabase_url, self.supabase_service_key)

    def get_user_id_from_token(self) -> str:
        """Extract user ID from JWT token."""
        if not self.auth_token:
            raise ValueError("No authentication token provided")
        
        try:
            # JWT tokens have three parts: header.payload.signature
            # We only need the payload
            payload = jwt.decode(self.auth_token, options={"verify_signature": False})
            return payload.get('sub')  # 'sub' is the user ID in Supabase JWTs
        except Exception as e:
            raise ValueError(f"Invalid authentication token: {str(e)}")

    async def create_token(self, organization_id: str, token_data: TokenCreate) -> Token:
        """Create a new token with optional expiration."""
        # Get user ID from token
        user_id = self.get_user_id_from_token()

        # Check if user is an admin of the organization (using regular client)
        admin_check = self.client.table('organization_members').select('*')\
            .eq('organization_id', organization_id)\
            .eq('user_id', user_id)\
            .eq('role', 'admin')\
            .execute()
            
        if not admin_check.data:
            raise ValueError("User is not an admin of this organization")

        # Calculate expiration time if specified
        expires_at = None
        if token_data.expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=token_data.expires_in_days)

        # Create service account token using admin client
        result = self.admin_client.rpc(
            'create_service_account_token',
            {
                'org_id': organization_id,
                'token_name': token_data.name,
                'created_by': user_id,
                'expires_at': expires_at.isoformat() if expires_at else None
            }
        ).execute()

        if not result.data:
            raise ValueError("Failed to create token")

        token_id = result.data[0]['token_id']
        jwt_token = result.data[0]['jwt_token']

        return Token(
            id=token_id,
            name=token_data.name,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            access_token=jwt_token
        )

    async def list_tokens(self, organization_id: str) -> List[Token]:
        """List all tokens for an organization."""
        result = self.client.table('tokens').select('*').eq('organization_id', organization_id).execute()
        return [Token(**token) for token in result.data]

    async def delete_token(self, token_id: str):
        """Delete a token."""
        self.client.table('tokens').delete().eq('id', token_id).execute()

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