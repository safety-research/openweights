from typing import Any, Dict, List, Optional, Union
import json
import os
import hashlib
from .validate import ApiConfig
from openweights.client.utils import guess_model_size, group_models_or_adapters_by_model, get_lora_rank
from openweights.client.temporary_api import TemporaryApi
from openweights import register, Jobs
import backoff
from transformers import AutoTokenizer


@register("api")
class API(Jobs):
    @backoff.on_exception(backoff.constant, Exception, interval=1, max_time=60, max_tries=60, on_backoff=lambda details: print(f"Retrying... {details['exception']}"))
    def create(self, requires_vram_gb='guess', allowed_hardware=None, **params) -> Dict[str, Any]:
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
        
        # Check if model needs a chat template
        # TODO: Improve logic.
        chat_template = None
        try:
            tokenizer = AutoTokenizer.from_pretrained(model)
            if tokenizer.chat_template is None:
                model_lower = model.lower()
                if 'llama' in model_lower:
                    template_tokenizer = AutoTokenizer.from_pretrained("unsloth/llama-3-8b-Instruct")
                    chat_template = template_tokenizer.chat_template
                    print("Using llama chat template")
                elif 'qwen' in model_lower:
                    template_tokenizer = AutoTokenizer.from_pretrained("unsloth/Qwen2.5-32B-Instruct-bnb-4bit")
                    chat_template = template_tokenizer.chat_template
                    print("Using qwen chat template")
        except Exception as e:
            print(f"Warning: Could not check tokenizer for {model}: {e}")

        script = (
            f"vllm serve {params['model']} \\\n"
            f"    --dtype auto \\\n"
            f"    --max-model-len {params['max_model_len']} \\\n"
            f"    --max-num-seqs {params['max_num_seqs']} \\\n"
            f"    --enable-prefix-caching \\\n"
            f"    --port 8000"
        )
        
        # Add chat template if needed
        if chat_template:
            # Escape the chat template for shell
            escaped_template = chat_template.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
            script += f' \\\n    --chat-template "{escaped_template}"'

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
            'allowed_hardware': allowed_hardware,
            'script': script,
            'docker_image': 'nielsrolf/ow-inference-v2:latest'
        }
        return self.get_or_create_or_reset(data)
    
    def deploy(self, model: str, lora_adapters: List[str] = None, max_lora_rank: str = 'guess', max_model_len: int = 2048, requires_vram_gb: str = 'guess', max_num_seqs: int = 100) -> TemporaryApi:
        """Deploy a model on OpenWeights"""
        if lora_adapters is None:
            lora_adapters = []
        if lora_adapters and max_lora_rank == 'guess':
            max_lora_rank = max(get_lora_rank(a) for a in lora_adapters)
        else:
            max_lora_rank = 16
        job = self.create(
            model=model, max_model_len=max_model_len, requires_vram_gb=requires_vram_gb,
            lora_adapters=lora_adapters, max_lora_rank=max_lora_rank, max_num_seqs=max_num_seqs)
        return TemporaryApi(self.client, job['id'])
    
    def multi_deploy(self, models: List[str], max_model_len: Union[int,str] = 2048, requires_vram_gb: Union[int,str] = 'guess', max_num_seqs: int = 100, base_model_override: Optional[str] = None) -> Dict[str, TemporaryApi]:
        """Deploy multiple models - creates on server for each base model, and deploys all lora adapters on of the same base model together"""
        assert isinstance(models, list), "models must be a list"
        lora_groups = group_models_or_adapters_by_model(models)
        apis = {}
        for model, lora_adapters in lora_groups.items():
            if base_model_override is not None:
                model = base_model_override
            print(f"Deploying {model} with {len(lora_adapters)} lora adapters")
            api = self.deploy(model, lora_adapters=lora_adapters, max_model_len=max_model_len, requires_vram_gb=requires_vram_gb, max_num_seqs=max_num_seqs)
            for model_id in [model] + lora_adapters:
                apis[model_id] = api
        return apis