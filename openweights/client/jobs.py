import json
from typing import BinaryIO, Dict, Any, List, Union
import os
from postgrest.exceptions import APIError
import hashlib
from supabase import Client

from openweights.validate import TrainingConfig, InferenceConfig, ApiConfig


class BaseJob:
    def __init__(self, supabase: Client, organization_id: str):
        self._supabase = supabase
        self._org_id = organization_id

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
    
    def restart(self, job_id: str) -> Dict[str, Any]:
        """Restart a job"""
        result = self._supabase.table('jobs').update({'status': 'pending'}).eq('id', job_id).execute()
        return result.data[0]
    
    def get_or_create_or_reset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """If job exists and is [pending, in_progress, completed] return it.
        If job exists and is [failed, canceled] reset it to pending and return it.
        If job doesn't exist, create it and return it.
        """
        # Always set organization_id from token
        data['organization_id'] = self._org_id
        
        try:
            result = self._supabase.table('jobs').select('*').eq('id', data['id']).single().execute()
        except APIError as e:
            if 'contains 0 rows' in str(e):
                result = self._supabase.table('jobs').insert(data).execute()
                return result.data[0]
            else:
                raise
        job = result.data

        # Assert that meta data is the same
        if 'meta' in data and 'meta' in job:
            assert data['meta'] == job['meta'], f"Job {data['id']} already exists with different meta data"
        elif 'meta' in job:
            result = self._supabase.table('jobs').update({'meta': job['meta']}).eq('id', data['id']).execute()
        elif 'meta' in data:
            job['meta'] = data['meta']

        if job['status'] in ['failed', 'canceled']:
            # Reset job to pending
            result = self._supabase.table('jobs').update(data).eq('id', data['id']).execute()
            return result.data[0]
        elif job['status'] in ['pending', 'in_progress', 'completed']:
            return job
        else:
            raise ValueError(f"Invalid job status: {job['status']}")
    
    def find(self, **params) -> List[Dict[str, Any]]:
        """Find jobs by their JSON values in job.params
        Example:
            jobs = client.jobs.find(training_file='result:file-abc123')
            jobs = client.jobs.find(meta={'group': 'hparams'})
        """
        query = self._supabase.table('jobs').select('*')
        
        for key, value in params.items():
            if isinstance(value, dict):
                # For nested dictionary values, use containedBy operator
                query = query.contains(f'params->{key}', value)
            else:
                # For simple values, use eq operator with ->> for JSON text extraction
                # ->> operator automatically handles string quoting
                query = query.eq(f'params->>{key}', value)
                
        data = query.execute().data

        return data
        
class FineTuningJobs(BaseJob):
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create a fine-tuning job"""
        if 'training_file' not in params:
            raise ValueError("training_file is required in params")
        
        if requires_vram_gb == 'guess':
            requires_vram_gb = 36 if '8b' in params['model'].lower() else 70
        
        hash_params = {k: v for k, v in params.items() if k not in ['meta']}
        job_id = f"ftjob-{hashlib.sha256(json.dumps(hash_params).encode()).hexdigest()[:12]}"

        if 'finetuned_model_id' not in params:
            model = params['model'].split('/')[-1]
            org = os.environ.get("HF_ORG") or os.environ.get("HF_USER")
            params['finetuned_model_id'] = f"{org}/{model}_{job_id}"
            
        params = TrainingConfig(**params).model_dump()

        data = {
            'id': job_id,
            'type': 'fine-tuning',
            'model': params['model'],
            'params': params,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'docker_image': 'nielsrolf/ow-unsloth:latest'
        }
        
        return self.get_or_create_or_reset(data)

class InferenceJobs(BaseJob):
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create an inference job"""

        hash_params = {k: v for k, v in params.items() if k not in ['meta']}
        job_id = f"ijob-{hashlib.sha256(json.dumps(hash_params).encode()).hexdigest()[:12]}"
        
        params = InferenceConfig(**params).model_dump()

        if requires_vram_gb == 'guess':
            requires_vram_gb = 150 if '70b' in params['model'].lower() else 24

        model = params['model']
        input_file_id = params['input_file_id']

        data = {
            'id': job_id,
            'type': 'inference',
            'model': model,
            'params': {**params, 'input_file_id': input_file_id},
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'docker_image': 'nielsrolf/ow-inference:latest'
        }
        
        return self.get_or_create_or_reset(data)

class Deployments(BaseJob):
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create an inference job"""
        params = ApiConfig(**params).model_dump()

        if requires_vram_gb == 'guess':
            requires_vram_gb = 150 if '70b' in params['model'].lower() else 24
        hash_params = dict(**params, requires_vram_gb=requires_vram_gb)
        job_id = f"apijob-{hashlib.sha256(json.dumps(hash_params).encode()).hexdigest()[:12]}"

        model = params['model']

        data = {
            'id': job_id,
            'type': 'api',
            'model': model,
            'params': params,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'docker_image': 'nielsrolf/ow-inference:latest'
        }
        
        return self.get_or_create_or_reset(data)
    
class Jobs(BaseJob):
    def create(self, script: Union[BinaryIO, str], requires_vram_gb: int, image='runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04') -> Dict[str, Any]:
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
            'requires_vram_gb': requires_vram_gb,
            'docker_image': image
        }
        
        return self.get_or_create_or_reset(data)