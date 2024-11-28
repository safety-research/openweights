import os
from typing import List, Optional
from supabase import create_client
from models import Job, Run, Worker, JobWithRuns, RunWithJobAndWorker, WorkerWithRuns
from openweights import OpenWeights
from dotenv import load_dotenv
import re


def is_progress_line(line):
    """
    Check if a line is likely a progress indicator that should be skipped
    """
    # Common patterns in progress lines
    progress_patterns = [
        r'⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏',  # Spinner characters
        r'\[#*\s*\]',  # Progress bars
        r'idealTree:.*',  # npm specific progress
        r'reify:.*',  # npm specific progress
        r'\([^)]*\)\s*�[⠀-⣿]',  # Progress with spinner
    ]
    
    return any(re.search(pattern, line) for pattern in progress_patterns)


def clean_ansi(text):
    # Step 1: Remove ANSI escape sequences
    ansi_escape = re.compile(r'''
        \x1B  # ESC
        (?:   # 7-bit C1 Fe (except CSI)
            [@-Z\\-_]
        |     # or [ for CSI
            \[
            [0-?]*  # parameter bytes
            [ -/]*  # intermediate bytes
            [@-~]   # final byte
        )
    ''', re.VERBOSE)
    
    text = ansi_escape.sub('', text)
    
    # Step 2: Split into lines and process terminal control characters
    lines = text.splitlines()
    screen = []
    current_line = ""
    
    for line in lines:
        # Handle carriage return (simulate line overwrites)
        if '\r' in line:
            parts = line.split('\r')
            # Process each part
            for part in parts:
                # Handle backspaces in this part
                while '\x08' in part:
                    part = re.sub(r'.\x08', '', part, 1)
                
                # Overwrite current line from the start
                current_line = part
        else:
            # Handle backspaces
            while '\x08' in line:
                line = re.sub(r'.\x08', '', line, 1)
            current_line = line
        
        # Only add non-empty lines that aren't just progress indicators
        if current_line.strip() and not is_progress_line(current_line):
            screen.append(current_line)
    
    # Remove duplicate consecutive lines
    unique_lines = []
    prev_line = None
    for line in screen:
        if line != prev_line:
            unique_lines.append(line)
            prev_line = line
    
    # If we have 0 lines because all where progress lines, return the last one
    if not unique_lines:
        return current_line
    
    # Join lines and clean up any remaining control characters
    cleaned_output = '\n'.join(unique_lines) + '\n'
    return cleaned_output


class Database:
    def __init__(self):
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        self.client = create_client(supabase_url, supabase_key)
        # Initialize OpenWeights client
        load_dotenv()
        self.ow_client = OpenWeights()

    def get_jobs(self, status: Optional[str] = None) -> List[Job]:
        query = self.client.table('jobs').select('*').order('created_at', desc=True)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        
        # Debug: Print jobs with outputs
        for job in result.data:
            if job.get('outputs'):
                print(f"Found job {job['id']} with outputs: {job['outputs']}")
        
        return [Job(**job) for job in result.data]

    def get_job(self, job_id: str) -> JobWithRuns:
        # Debug: Print the raw SQL query
        print(f"Fetching job with ID: {job_id}")
        
        # First, get just the job to see its raw data
        job_result = self.client.table('jobs').select('*').eq('id', job_id).execute()
        print(f"Raw job data: {job_result.data}")
        
        # Now get the job with runs
        job = self.client.table('jobs').select('*').eq('id', job_id).single().execute()
        runs = self.client.table('runs').select('*').eq('job_id', job_id).order('created_at', desc=True).execute()
        
        # Debug: Print the complete job data
        print(f"Complete job data: {job.data}")
        print(f"Job outputs: {job.data.get('outputs')}")
        
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

    def format_training_metrics(self, data: dict) -> str:
        """Format training metrics in a readable way."""
        # Group metrics by category
        groups = {
            "Progress": ['step', 'epoch'],
            "Training": ['loss', 'nll_loss', 'grad_norm', 'learning_rate'],
            "Rewards": ['rewards/accuracies', 'rewards/margins', 'rewards/chosen', 'rewards/rejected'],
            "Model Outputs": ['logps/chosen', 'logps/rejected', 'logits/chosen', 'logits/rejected', 'log_odds_ratio', 'log_odds_chosen']
        }
        
        parts = []
        
        # Format each group
        for group_name, metrics in groups.items():
            group_parts = []
            for metric in metrics:
                if metric in data:
                    value = data[metric]
                    if metric in ['step', 'epoch']:
                        # Format step as integer, epoch with fewer decimals
                        if metric == 'step':
                            group_parts.append(f"{metric}={int(value)}")
                        else:
                            group_parts.append(f"{metric}={value:.3f}")
                    elif isinstance(value, float):
                        if 'learning_rate' in metric:
                            group_parts.append(f"{metric}={value:.1e}")
                        else:
                            group_parts.append(f"{metric}={value:.4f}")
                    else:
                        group_parts.append(f"{metric}={value}")
            
            if group_parts:
                parts.append(f"{group_name}: {' | '.join(group_parts)}")
        
        # Add any remaining metrics not in groups
        other_metrics = []
        for key, value in data.items():
            if not any(key in group_metrics for group_metrics in groups.values()):
                if isinstance(value, float):
                    other_metrics.append(f"{key}={value:.4f}")
                else:
                    other_metrics.append(f"{key}={value}")
        
        if other_metrics:
            parts.append(f"Other: {' | '.join(other_metrics)}")
        
        return "\n    ".join(parts)

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