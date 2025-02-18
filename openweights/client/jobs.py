import re
import json
from typing import BinaryIO, Dict, Any, List, Union, Tuple
import os
from postgrest.exceptions import APIError
import backoff

import hashlib
from supabase import Client

from openweights.client.utils import resolve_lora_model, get_lora_rank


class BaseJob:
    def __init__(self, supabase: Client, organization_id: str):
        self._supabase = supabase
        self._org_id = organization_id

    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List jobs"""
        result = self._supabase.table('jobs').select('*').order('updated_at', desc=True).limit(limit).execute()
        return result.data

    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def retrieve(self, job_id: str) -> Dict[str, Any]:
        """Get job details"""
        result = self._supabase.table('jobs').select('*').eq('id', job_id).single().execute()
        return result.data

    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def cancel(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job"""
        result = self._supabase.table('jobs').update({'status': 'canceled'}).eq('id', job_id).execute()
        return result.data[0]
    
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def restart(self, job_id: str) -> Dict[str, Any]:
        """Restart a job"""
        result = self._supabase.table('jobs').update({'status': 'pending'}).eq('id', job_id).execute()
        return result.data[0]
    
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
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
        
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
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
            elif isinstance(value, bool):
                # Convert boolean to lowercase string for JSON comparison
                query = query.eq(f'params->>{key}', str(value).lower())
            else:
                # For simple values, use eq operator with ->> for JSON text extraction
                query = query.eq(f'params->>{key}', value)
                
        data = query.execute().data

        return data



    
class Jobs(BaseJob):
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, script: Union[BinaryIO, str], requires_vram_gb: int, image='nielsrolf/ow-unsloth:latest', type='script', params=None) -> Dict[str, Any]:
        """Create a script job"""
        
        if isinstance(script, (str, bytes)):
            script_content = script
        else:
            script_content = script.read()
        if isinstance(script_content, bytes):
            script_content = script_content.decode('utf-8')

        job_id = f"sjob-{hashlib.sha256(script_content.encode() + self._org_id.encode()).hexdigest()[:12]}"
        
        data = {
            'id': job_id,
            'type': type,
            'script': script_content,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'docker_image': image,
            'params': params or {}
        }
        
        return self.get_or_create_or_reset(data)