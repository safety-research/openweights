import os
from openweights import OpenWeights
import openweights.jobs.axolotl


ow = OpenWeights()
job = ow.axolotl.create(
    local_config_dir=os.path.dirname(__file__),
    command="axolotl train qwen25.yaml",
    allowed_hardware=['8x H100', '8x H100S', '8x H100N', '8x H200']
)
print(job)
