import argparse
import os
import json
from pydantic import BaseModel, Field
from openweights import OpenWeights, register, Jobs
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List
from dotenv import load_dotenv
import yaml

from .validate import AxolotlConfig


def merge_dicts(dict1, dict2):
    """Recursively merge two dictionaries."""
    for key, value in dict2.items():
        if isinstance(value, dict) and key in dict1:
            dict1[key] = merge_dicts(dict1[key], value)
        else:
            dict1[key] = value
    return dict1


@register("axolotl")
class Axolotl(Jobs):
    base_image = 'nielsrolf/ow-axolotl'
    mount = {
        os.path.join(os.path.dirname(__file__), 'push_to_hub.py'): 'push_to_hub.py',
    }

    def create(self, mount_dir, config_yaml, allowed_hardware, **config_overrides):
        """Create an axolotl
        
        Arguments:
            mount_dir: str - The local directory containing the config.yaml file, the training file, deepseep config files if needed, etc
            config_yaml: str - The path to the main axolotl config file
                For consistency with the unsloth finetuning jobs, the hub_model_id will be set automatically to f"{HF_ORG}/{base_model_repo}-{job_id}"
                When a hf_hub_id is specified in the config.yaml, it will be used as format string and HF_ORG, base_model_repo and job_id will be used as format arguments
            allowed_hardware: List[str] - The allowed hardware for the job, eg ['2x A100', '8x H100']
        """
        mounted_files = self._upload_mounted_files(self.mount)
        mounted_files.update(self._upload_mounted_files({mount_dir: '.'}))
        with open(config_yaml, 'r') as file:
            config_data = yaml.safe_load(file)
        config_data = merge_dicts(config_data, config_overrides)
        job_id = self.compute_id({
            'mounted_files': mounted_files,
            'config': config_data
        })
        
        model = config_data['base_model']
        config_data['output_dir'] = config_data.get('output_dir', f"./outputs")
        finetuned_model_id = config_data.get('hf_hub_id', "{HF_ORG}/{base_model_repo}-{job_id}").format(
            HF_ORG=self.client.hf_org,
            base_model_repo=model.split('/')[-1],
            job_id=job_id
        )
        config_data['hf_hub_id'] = finetuned_model_id
        validated_config = AxolotlConfig(**config_data)
        
        with open(f"{job_id}.yaml", 'w') as file:
            yaml.dump(config_data, file)
        mounted_files.update(self._upload_mounted_files({f"{job_id}.yaml": f"{job_id}.yaml"}))
        command = (
            f"axolotl train {job_id}.yaml && touch completed\n"
            f"python push_to_hub.py {config_data['output_dir']} {finetuned_model_id} "
        )
        
        job_data = {
            'id': job_id,
            'type': 'custom',
            'docker_image': self.base_image,
            'allowed_hardware': allowed_hardware,
            'script': command,
            'params': {
                'model': config_data['base_model'],
                'finetuned_model_id': finetuned_model_id,
                'command': command,
                'mounted_files': mounted_files
            },
            'model': config_data['base_model'],
        }
            
        return self.get_or_create_or_reset(job_data)
