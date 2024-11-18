from typing import Optional, BinaryIO, Dict, Any, List
import os
from supabase import create_client, Client
import hashlib
from datetime import datetime

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
        file_id = self._calculate_file_hash(file)

        # If the file already exists, return the existing file
        try:
            existing_file = self._supabase.table('files').select('*').eq('id', file_id).single().execute().data
            if existing_file:
                return existing_file
        except:
            pass  # File doesn't exist yet, continue with creation

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
    def create(self, model: str, params: Dict[str, Any], requires_vram_gb=48) -> Dict[str, Any]:
        """Create a fine-tuning job"""
        if 'training_file' not in params:
            raise ValueError("training_file is required in params")

        job_id = f"ftjob-{hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:12]}"
        
        data = {
            'id': job_id,
            'type': 'fine-tuning',
            'model': model,
            'params': params,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb
        }
        
        result = self._supabase.table('jobs').insert(data).execute()
        return result.data[0]

class InferenceJobs(BaseJob):
    def create(self, input_file_id: str, model: str, params: Dict[str, Any], requires_vram_gb=24) -> Dict[str, Any]:
        """Create an inference job"""
        job_id = f"ijob-{hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:12]}"
        
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
    def create(self, script: BinaryIO) -> Dict[str, Any]:
        """Create a script job"""
        job_id = f"sjob-{hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:12]}"
        
        script_content = script.read()
        if isinstance(script_content, bytes):
            script_content = script_content.decode('utf-8')
        
        data = {
            'id': job_id,
            'type': 'script',
            'script': script_content,
            'status': 'pending',
            'requires_vram_gb': 24
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
        self.fine_tuning = type('FineTuning', (), {'jobs': FineTuningJobs(self._supabase)})()
        self.inference = InferenceJobs(self._supabase)
        self.jobs = Jobs(self._supabase)
        self.runs = Runs(self._supabase)

