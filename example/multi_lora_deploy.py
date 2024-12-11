from openweights import OpenWeights # type: ignore
from dotenv import load_dotenv # type: ignore

load_dotenv()
ow = OpenWeights()

lora_adapters = [
    'nielsrolf/llama-3-8b-Instruct_ftjob-d0f3770974cb',
    'nielsrolf/llama-3-8b-Instruct_ftjob-bb1d2c5d7bea'
]

apis = ow.multi_deploy(lora_adapters)
