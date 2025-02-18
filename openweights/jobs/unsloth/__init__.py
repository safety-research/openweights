from openweights import register, CustomJob


@register("fine_tuning")        
class FineTuning(CustomJob):
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, requires_vram_gb='guess', **params) -> Dict[str, Any]:
        """Create a fine-tuning job"""
        if 'training_file' not in params:
            raise ValueError("training_file is required in params")
        
        if requires_vram_gb == 'guess':
            requires_vram_gb = 36 if '8b' in params['model'].lower() else 70
        
        job_id, params = self._prepare_job_params(params)

        data = {
            'id': job_id,
            'type': 'fine-tuning',
            'model': params['model'],
            'params': params,
            'status': 'pending',
            'requires_vram_gb': requires_vram_gb,
            'docker_image': 'nielsrolf/ow-unsloth-v2:latest'
        }
        
        return self.get_or_create_or_reset(data)

    def get_training_config(self, **params) -> Dict[str, Any]:
        """Get the training config for a fine-tuning job"""
        _, params = self._prepare_job_params(params)
        return params

    def _prepare_job_params(self, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Prepare job parameters and generate job ID"""
        hash_params = {k: v for k, v in params.items() if k not in ['meta']}
        job_id = f"ftjob-{hashlib.sha256(json.dumps(hash_params).encode() + self._org_id.encode()).hexdigest()[:12]}"
        
        if 'finetuned_model_id' not in params:
            model = params['model'].split('/')[-1]
            org = os.environ.get("HF_ORG") or os.environ.get("HF_USER")
            params['finetuned_model_id'] = f"{org}/{model}_{job_id}"
        
        params = TrainingConfig(**params).model_dump()
        return job_id, params