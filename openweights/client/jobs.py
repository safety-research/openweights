import re
import json
from typing import BinaryIO, Dict, Any, List, Union
import os
from postgrest.exceptions import APIError
import backoff

import hashlib
from supabase import Client

from openweights.validate import TrainingConfig, InferenceConfig, ApiConfig


class BaseJob:
    def __init__(self, supabase: Client, organization_id: str):
        self._supabase = supabase
        self._org_id = organization_id

    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List jobs"""
        result = self._supabase.table('jobs').select('*').limit(limit).execute()
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
        
class FineTuningJobs(BaseJob):
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create a fine-tuning job"""
        if 'training_file' not in params:
            raise ValueError("training_file is required in params")
        
        if requires_vram_gb == 'guess':
            requires_vram_gb = 36 if '8b' in params['model'].lower() else 70
        
        hash_params = {k: v for k, v in params.items() if k not in ['meta']}
        job_id = f"ftjob-{hashlib.sha256(json.dumps(hash_params).encode() + self._org_id.encode()).hexdigest()[:12]}"

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
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create an inference job"""

        hash_params = {k: v for k, v in params.items() if k not in ['meta']}
        job_id = f"ijob-{hashlib.sha256(json.dumps(hash_params).encode() + self._org_id.encode()).hexdigest()[:12]}"
        
        params = InferenceConfig(**params).model_dump()

        if requires_vram_gb == 'guess':
            model_size = guess_model_size(params['model'])
            weights_require = 2 * model_size
            if '8bit' in params['model'] and not 'ftjob' in params['model']:
                weights_require = weights_require / 2
            elif '4bit' in params['model'] and not 'ftjob' in params['model']:
                weights_require = weights_require / 4
            kv_cache_requires = 5 # TODO estimate this better
            requires_vram_gb = int(weights_require + kv_cache_requires + 0.5)

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

def guess_model_size(model: str) -> int:
    """Guess the model size in billions of parameters from the name"""
    # Use regex to extract the model size from the model name
    if 'mistral-small' in model.lower():
        return 22
    match = re.search(r'(\d+)([bB])', model)
    if match:
        model_size = int(match.group(1))
        return model_size
    else:
        print(f"Could not guess model size from model name: {model}. Defaulting to 32B")
        return 32


class Deployments(BaseJob):
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create an inference job"""
        params = ApiConfig(**params).model_dump()

        if requires_vram_gb == 'guess':
            model_size = guess_model_size(params['model'])
            weights_require = 2 * model_size
            if '8bit' in params['model']:
                weights_require = weights_require / 2
            elif '4bit' in params['model']:
                weights_require = weights_require / 4
            loras_require = params['max_loras'] * params['max_lora_rank'] / 16
            kv_cache_requires = 5 # TODO estimate this better
            requires_vram_gb = int(weights_require + loras_require + kv_cache_requires + 0.5)

        hash_params = dict(**params, requires_vram_gb=requires_vram_gb)
        job_id = f"apijob-{hashlib.sha256(json.dumps(hash_params).encode() + self._org_id.encode()).hexdigest()[:12]}"

        model = params['model']

        script = (
            f"vllm serve {params['model']} \\\n"
            f"    --dtype auto \\\n"
            f"    --max-model-len {params['max_model_len']} \\\n"
            f"    --max-num-seqs {params['max_num_seqs']} \\\n"
            f"    --enable-prefix-caching \\\n"
            f"    --port 8000"
        )

        if "bnb-4bit" in params['model']:
            script += (
                f" \\\n"
                f"    --quantization=bitsandbytes \\\n"
                f"    --load-format=bitsandbytes \\\n"
                f"    --tensor-parallel-size 1 \\\n"
                f"    --pipeline-parallel-size $N_GPUS"
            )
        else:
            script += f" \\\n"
            script += f"    --tensor-parallel-size $N_GPUS"


        if params['lora_adapters']:
            script += (
                f" \\\n"
                f"    --enable-lora \\\n"
                f"    --max-lora-rank {params['max_lora_rank']} \\\n"
                f"    --max-loras {params['max_loras']} \\\n"
                f"    --lora-modules \\\n"
            )
            for adapter in params['lora_adapters']:
                script += f"        {adapter}={adapter} \\\n"

        data = {
            'id': job_id,
            'type': 'api',
            'model': model,
            'params': params,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'script': script,
            'docker_image': 'nielsrolf/ow-inference:latest'
        }
        return self.get_or_create_or_reset(data)

    
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