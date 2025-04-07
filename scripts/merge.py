import os
from huggingface_hub import snapshot_download
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# Define model paths
base_model_id = "unsloth/Qwen2.5-Coder-32B-Instruct"
adapter_model_id = "longtermrisk/Qwen2.5-Coder-32B-Instruct-ftjob-2da7cc54fd8f"
adapter_checkpoint = "checkpoint-100"
output_dir = "merged_model"

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Download the adapter checkpoint if needed
adapter_path = os.path.join(adapter_model_id, adapter_checkpoint)
if not os.path.exists(adapter_path):
    print(f"Downloading adapter checkpoint {adapter_checkpoint}...")
    adapter_path = snapshot_download(
        repo_id=adapter_model_id,
        allow_patterns=f"{adapter_checkpoint}/**"
    )
    adapter_path = os.path.join(adapter_path, adapter_checkpoint)

# Load base model
print(f"Loading base model from {base_model_id}...")
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)

# Load and merge with LoRA adapter
print(f"Loading and merging with adapter from {adapter_path}...")
model = PeftModel.from_pretrained(base_model, adapter_path)
model = model.merge_and_unload()

# Save the merged model
print(f"Saving merged model to {output_dir}...")
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)

print("Model merging completed successfully!")