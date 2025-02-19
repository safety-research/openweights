from openweights import register, Jobs
from typing import Any, Dict, Tuple
import hashlib
import json
import os
import backoff
from glob import glob

from .validate import TrainingConfig


@register("fine_tuning")        
class FineTuning(Jobs):

    mount = {
        filepath: os.path.basename(filepath)
        for filepath in glob(os.path.join(os.path.dirname(__file__), '*.py'))
    }
    base_image: str = 'nielsrolf/ow-unsloth-v2'

    @property
    def id_predix(self):
        return 'ftjob'

    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create a fine-tuning job"""
        if 'training_file' not in params:
            raise ValueError("training_file is required in params")
        
        if requires_vram_gb == 'guess':
            requires_vram_gb = 36 if '8b' in params['model'].lower() else 70
        
        params = TrainingConfig(**params).model_dump()
        mounted_files = self._upload_mounted_files()
        job_id = self.compute_id({
            'validated_params': params,
            'mounted_files': mounted_files
        })
        model_name = params['model'].split('/')[-1]
        hf_org = os.getenv('HF_ORG') or os.getenv('HF_USER')
        params['finetuned_model_id'] = params['finetuned_model_id'].format(job_id=job_id, org_id=hf_org, model_name=model_name)

        data = {
            'id': job_id,
            'type': 'fine-tuning',
            'model': params['model'],
            'params': {
                'validated_params': params,
                'mounted_files': mounted_files
            },
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'docker_image': self.base_image,
            'script': self.get_entrypoint(TrainingConfig(**params))
        }
        
        return self.get_or_create_or_reset(data)

    def get_training_config(self, **params) -> Dict[str, Any]:
        """Get the training config for a fine-tuning job"""
        _, params = self._prepare_job_params(params)
        return params
    
    def get_entrypoint(self, config: TrainingConfig) -> str:
        return f"python training.py '{json.dumps(config.model_dump())}'"