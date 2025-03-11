import os
from openweights import OpenWeights
import openweights.jobs.axolotl


ow = OpenWeights()
job = ow.axolotl.create(
    local_config_dir=os.path.dirname(__file__),
    command='axolotl train llama_3_70b_fft.yaml',
    allowed_hardware=['8x H100', '8x A100', '8x H100S', '8x H100N', '8x A100S']
)
print(job)
