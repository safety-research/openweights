import os
from openweights import OpenWeights
import openweights.jobs.axolotl


ow = OpenWeights()
job = ow.axolotl.create(
    mount_dir=os.path.dirname(__file__),
    config_yaml="qwen25.yaml",
    allowed_hardware=['1x H100']
)
print(job)
