import os
from openweights import OpenWeights
import openweights.jobs.axolotl

command = """axolotl train config.yaml"""
ow = OpenWeights()
job = ow.axolotl.create(
    local_config_dir=os.path.dirname(__file__),
    command=command,
    allowed_hardware=['8x H100', '8x H100S', '8x H100N', '8x H200']
)
print(job)
