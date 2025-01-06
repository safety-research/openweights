import os
import json
from pydantic import BaseModel, Field
from openweights import OpenWeights
from openweights.client.custom_job import CustomJob
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List
from dotenv import load_dotenv

load_dotenv()
client = OpenWeights()


class GuidedInferenceConfig(BaseModel):
    class Config:
        extra = "forbid"  # Prevent extra fields not defined in the model

    model: str = Field(..., description="Hugging Face model ID")
    input_file_id: str = Field(..., description="File ID of the input dataset")

    max_tokens: int = Field(600, description="Maximum number of tokens to generate")
    temperature: float = Field(1.0, description="Temperature for sampling")
    top_p: float = Field(1.0, description="Top P")
    stop: List[str] = Field([], description="Stop sequences")
    prefill: str = Field('', description="Prefill")
    min_tokens: int = Field(1, description="Minimum number of tokens to generate")
    max_model_len: int = Field(2048, description="Maximum model length")

    @field_validator("input_file_id")
    def validate_dataset_type(cls, v, info):
        if not v:  # Skip validation if dataset is not provided (test_dataset is optional)
            return v
        # Validate based on training type
        if not v.startswith('conversations'):
            raise ValueError(f"Inference jobs require dataset type to be 'conversations', got: {v}")
        return v



class GuidedInferenceJob(CustomJob):
    # Mount our addition script
    mount = {
        os.path.join(os.path.dirname(__file__), 'guided_inference.py'): 'guided_inference2.py'
    }
    
    # Define parameter validation using our Pydantic model
    params = GuidedInferenceConfig
    
    base_image = 'nielsrolf/ow-inference' # We have to use an ow worker image - you can build your own by using something similar to the existing Dockerfiles
    
    requires_vram_gb = 0

    def get_entrypoint(self, validated_params: GuidedInferenceConfig) -> str:
        """Create the command to run our script with the validated parameters"""
        # Convert parameters to JSON string to pass to script
        params_json = json.dumps(validated_params.model_dump())
        return f'python guided_inference2.py \'{params_json}\''


def main():
    # Initialize OpenWeights client
    client = OpenWeights()

    # Upload inference file
    with open('messages.jsonl', 'rb') as file:
        file = client.files.create(file, purpose="conversations")
    file_id = file['id']

    # Create an inference job
    job = GuidedInferenceJob(client).create(
        model='unsloth/llama-3-8b-Instruct',
        input_file_id=file_id,
        max_tokens=1000,
        temperature=0,
        max_model_len=2048
    )
    
    # Optional: wait for job completion and print results
    import time
    while True:
        job = client.jobs.retrieve(job['id'])
        if job['status'] in ['completed', 'failed']:
            break
        print("Waiting for job completion...")
        time.sleep(2)
    
    if job['status'] == 'completed':
        print(f"Job completed successfully: {job['outputs']}") # Will contain the latest event data: {'result': 8.0}
        # Get the results from the events
        events = client.events.list(job_id=job['id'])
        for event in events:
            print(f"Event data: {event['data']}")
    else:
        print(f"Job failed: {job}")


if __name__ == '__main__':
    main()