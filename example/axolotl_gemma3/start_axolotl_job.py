import os
from openweights import OpenWeights
import openweights.jobs.axolotl

command = """pip install git+https://github.com/axolotl-ai-cloud/axolotl
axolotl train config.yaml"""
ow = OpenWeights()
job = ow.axolotl.create(
    local_config_dir=os.path.dirname(__file__),
    command=command,
    allowed_hardware=['8x H100', '8x H100S', '8x H100N']
)
print(job)
