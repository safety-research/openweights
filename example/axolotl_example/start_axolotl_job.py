import os
from openweights import OpenWeights
import openweights.jobs.axolotl


ow = OpenWeights()
job = ow.axolotl.create(
    mount_dir=os.path.dirname(__file__),
    # config_yaml="qwen25.yaml",
    config_yaml="llama_3_70b_fft.yaml",
    allowed_hardware=['4x H200']
)
print(job)
