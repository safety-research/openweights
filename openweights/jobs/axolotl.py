import argparse
import os
import json
from pydantic import BaseModel, Field
from openweights import OpenWeights, register, Jobs
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List
from dotenv import load_dotenv


@register("axolotl")
class Axolotl(Jobs):
    base_image = 'nielsrolf/ow-axolotl'

    def create(self, local_config_dir, allowed_hardware, command='axolotl train config.yaml'):
        """Create an axolotl
        
        local_config_dir: str - The local directory containing the config.yaml file, the training file, deepseep config files if needed, etc
        command: str - The command that will be run in a copy of the local_config_dir
        allowed_hardware: List[str] - The allowed hardware for the job, eg ['2x A100', '8x H100']
        """
        mounted_files = self._upload_mounted_files({local_config_dir: '.'})
        job_data = {
            'type': 'custom',
            'docker_image': self.base_image,
            'allowed_hardware': allowed_hardware,
            'script': command,
            'params': {
                'command': command,
                'mounted_files': mounted_files
            }
        }
            
        return self.get_or_create_or_reset(job_data)