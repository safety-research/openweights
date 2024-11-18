from openweights import OpenWeights
from dotenv import load_dotenv

load_dotenv()


client = OpenWeights()

job = client.jobs.create(
    script=open('script.sh'),
    requires_vram_gb=0
)

print(job)


