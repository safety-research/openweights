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


@register("axolotl")
class Axolotl(Jobs):
    base_image = 'nielsrolf/ow-axolotl'

    def create(self, mount_dir, config_yaml, allowed_hardware):
        """Create an axolotl
        
        Arguments:
            mount_dir: str - The local directory containing the config.yaml file, the training file, deepseep config files if needed, etc
            config_yaml: str - The path to the main axolotl config file
                For consistency with the unsloth finetuning jobs, the hub_model_id will be set automatically to f"{HF_ORG}/{base_model_repo}-{job_id}"
                When a hf_hub_id is specified in the config.yaml, it will be used as format string and HF_ORG, base_model_repo and job_id will be used as format arguments
            allowed_hardware: List[str] - The allowed hardware for the job, eg ['2x A100', '8x H100']



        """
        mounted_files = self._upload_mounted_files({mount_dir: '.'})
        command = f"axolotl train {config_yaml}"
        with open(config_yaml, 'r') as file:
            config_data = yaml.safe_load(file)
        model = config_data['base_model']
        finetuned_model_id = config_data.get('hf_hub_id', "{HF_ORG}/{base_model_repo}-{job_id}").format(
            HF_ORG=self.client.hf_org,
            base_model_repo=model.split('/')[-1],
            job_id=self.compute_id({
                'mounted_files': mounted_files,
                'command': command,
                'config': config_data
            })
        )
        config_data['hf_hub_id'] = finetuned_model_id
        with open(config_yaml, 'w') as file:
            yaml.dump(config_data, file)
        mounted_files.update(self._upload_mounted_files({config_yaml: config_yaml}))
        
        job_data = {
            'type': 'custom',
            'docker_image': self.base_image,
            'allowed_hardware': allowed_hardware,
            'script': command,
            'params': {
                'model': config_data['base_model'],
                'finetuned_model_id': finetuned_model_id,
                'command': command,
                'mounted_files': mounted_files
            }
        }
            
        return self.get_or_create_or_reset(job_data)