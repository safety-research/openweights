from typing import Optional, BinaryIO, Dict, Any, List, Union
import os
import sys
from supabase import create_client, Client
from postgrest.exceptions import APIError
import hashlib
from datetime import datetime

from openweights.validate import validate_messages, validate_preference_dataset, TrainingConfig, InferenceConfig


class Files:
    def __init__(self, supabase: Client):
        self._supabase = supabase
    
    def _calculate_file_hash(self, file: BinaryIO) -> str:
        """Calculate SHA-256 hash of file content"""
        sha256_hash = hashlib.sha256()
        for byte_block in iter(lambda: file.read(4096), b""):
            sha256_hash.update(byte_block)
        file.seek(0)  # Reset file pointer
        return f"file-{sha256_hash.hexdigest()[:12]}"

    def create(self, file: BinaryIO, purpose: str) -> Dict[str, Any]:
        """Upload a file and create a database entry"""
        file_id = f"{purpose}:{self._calculate_file_hash(file)}"

        # If the file already exists, return the existing file
        try:
            existing_file = self._supabase.table('files').select('*').eq('id', file_id).single().execute().data
            if existing_file:
                return existing_file
        except:
            pass  # File doesn't exist yet, continue with creation

        # Validate file content
        if not self.validate(file, purpose):
            raise ValueError("File content is not valid")

        file_size = os.fstat(file.fileno()).st_size
        filename = getattr(file, 'name', 'unknown')

        # Store file in Supabase Storage
        self._supabase.storage.from_('files').upload(
            path=file_id,
            file=file
        )

        # Create database entry
        data = {
            'id': file_id,
            'filename': filename,
            'purpose': purpose,
            'bytes': file_size
        }
        
        result = self._supabase.table('files').insert(data).execute()
        
        return {
            'id': file_id,
            'object': 'file',
            'bytes': file_size,
            'created_at': datetime.now().timestamp(),
            'filename': filename,
            'purpose': purpose,
        }

    def content(self, file_id: str) -> bytes:
        """Get file content"""
        return self._supabase.storage.from_('files').download(file_id)
    
    def validate(self, file: BinaryIO, purpose: str) -> bool:
        """Validate file content"""
        if purpose in ['conversations']:
            content = file.read().decode('utf-8')
            return validate_messages(content)
        elif purpose == 'preference':
            content = file.read().decode('utf-8')
            return validate_preference_dataset(content)
        else:
            return True

class Run:
    def __init__(self, supabase: Client, job_id: Optional[str] = None):
        self._supabase = supabase
        self.id = os.getenv('OPENWEIGHTS_RUN_ID')
        
        if self.id:
            # Run ID exists, fetch the data
            try:
                result = self._supabase.table('runs').select('*').eq('id', self.id).single().execute()
            except APIError as e:
                if 'contains 0 rows' in str(e):
                    raise ValueError(f"Run with ID {self.id} not found")
                raise
            
            run_data = result.data
            if job_id and run_data['job_id'] != job_id:
                breakpoint()
                raise ValueError(f"Run {self.id} is associated with job {run_data['job_id']}, not {job_id}")
            
            self._load_data(run_data)
        else:
            # Create new run
            data = {
                'status': 'in_progress'
            }
            
            if job_id:
                data['job_id'] = job_id
            else:
                # Create a new script job
                command = ' '.join(sys.argv)
                job_data = {
                    'id': f"sjob-{hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:12]}",
                    'type': 'script',
                    'script': command,
                    'status': 'in_progress'
                }
                job_result = self._supabase.table('jobs').insert(job_data).execute()
                data['job_id'] = job_result.data[0]['id']
            
            result = self._supabase.table('runs').insert(data).execute()
            self._load_data(result.data[0])

    def _load_data(self, data: Dict[str, Any]):
        self.id = data['id']
        self.job_id = data['job_id']
        self.worker_id = data.get('worker_id')
        self.status = data['status']
        self.log_file = data.get('log_file')
        self.created_at = data['created_at']

    @staticmethod
    def get(supabase: Client, run_id: int) -> 'Run':
        """Get a run by ID"""
        run = Run(supabase)
        run.id = run_id
        try:
            result = supabase.table('runs').select('*').eq('id', run_id).single().execute()
        except APIError as e:
            if 'contains 0 rows' in str(e):
                raise ValueError(f"Run with ID {run_id} not found")
            raise
        run._load_data(result.data)
        return run

    def update(self, status: Optional[str] = None, logfile: Optional[str] = None):
        """Update run status and/or logfile"""
        data = {}
        if status:
            data['status'] = status
        if logfile:
            data['log_file'] = logfile
        
        if data:
            result = self._supabase.table('runs').update(data).eq('id', self.id).execute()
            self._load_data(result.data[0])

    def log(self, event_data: Dict[str, Any]):
        """Log an event for this run"""
        data = {
            'run_id': self.id,
            'data': event_data
        }
        self._supabase.table('events').insert(data).execute()

class BaseJob:
    def __init__(self, supabase: Client):
        self._supabase = supabase

    def list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List jobs"""
        result = self._supabase.table('jobs').select('*').limit(limit).execute()
        return result.data

    def retrieve(self, job_id: str) -> Dict[str, Any]:
        """Get job details"""
        result = self._supabase.table('jobs').select('*').eq('id', job_id).single().execute()
        return result.data

    def cancel(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job"""
        result = self._supabase.table('jobs').update({'status': 'canceled'}).eq('id', job_id).execute()
        return result.data[0]

class FineTuningJobs(BaseJob):
    def create(self, requires_vram_gb=48, **params) -> Dict[str, Any]:
        """Create a fine-tuning job"""
        if 'training_file' not in params:
            raise ValueError("training_file is required in params")
        
        job_id = f"ftjob-{hashlib.sha256(json.dumps(params).encode()).hexdigest()[:12]}"
        if 'finetuned_model_id' not in params:
            params['finetuned_model_id'] = f"model:{job_id}"
        params = TrainingConfig(**params).model_dump()

        data = {
            'id': job_id,
            'type': 'fine-tuning',
            'model': params['model'],
            'params': params,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb
        }
        
        result = self._supabase.table('jobs').insert(data).execute()
        return result.data[0]

class InferenceJobs(BaseJob):
    def create(self, requires_vram_gb=24, **params) -> Dict[str, Any]:
        """Create an inference job"""
        job_id = f"ijob-{hashlib.sha256(json.dumps(params).encode()).hexdigest()[:12]}"
        
        params = InferenceConfig(**params).model_dump()

        model = params['model']
        input_file_id = params['input_file_id']

        data = {
            'id': job_id,
            'type': 'inference',
            'model': model,
            'params': {**params, 'input_file_id': input_file_id},
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb
        }
        
        result = self._supabase.table('jobs').insert(data).execute()
        return result.data[0]

class Jobs(BaseJob):
    def create(self, script: Union[BinaryIO, str], requires_vram_gb) -> Dict[str, Any]:
        """Create a script job"""
        
        if isinstance(script, (str, bytes)):
            script_content = script
        else:
            script_content = script.read()
        if isinstance(script_content, bytes):
            script_content = script_content.decode('utf-8')

        job_id = f"sjob-{hashlib.sha256(script_content.encode()).hexdigest()[:12]}"
        
        data = {
            'id': job_id,
            'type': 'script',
            'script': script_content,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb
        }
        
        result = self._supabase.table('jobs').insert(data).execute()
        return result.data[0]

class Runs:
    def __init__(self, supabase: Client):
        self._supabase = supabase

    def list(self, job_id: Optional[str] = None, worker_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """List runs by job_id or worker_id"""
        query = self._supabase.table('runs').select('*').limit(limit)
        if job_id:
            query = query.eq('job_id', job_id)
        if worker_id:
            query = query.eq('worker_id', worker_id)
        result = query.execute()
        return result.data

class OpenWeights:
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        """Initialize OpenWeights client"""
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase URL and key must be provided either as arguments or environment variables")
        
        self._supabase = create_client(self.supabase_url, self.supabase_key)
        
        # Initialize components
        self.files = Files(self._supabase)
        self.fine_tuning = FineTuningJobs(self._supabase)
        self.inference = InferenceJobs(self._supabase)
        self.jobs = Jobs(self._supabase)
        self.runs = Runs(self._supabase)

        self._current_run = None
    
    @property
    def run(self):
        if not self._current_run:
            self._current_run = Run(self._supabase)
        return self._current_run