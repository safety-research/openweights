import json
import os

import torch
from dotenv import load_dotenv
from transformers import AutoTokenizer, TrainerCallback
from functools import wraps

from openweights.client import OpenWeights

load_dotenv()


client = OpenWeights()


def get_chat_template_for_model(model_id, tokenizer):
    """Get appropriate chat template for a model that doesn't have one.
    
    Args:
        model_id: The model identifier
        tokenizer: The tokenizer instance
        
    Returns:
        A chat template string for specific model types if the tokenizer
        doesn't already have a chat_template, otherwise None.
    """
    if tokenizer.chat_template is not None:
        return None
    
    model_lower = model_id.lower()
    if 'llama' in model_lower:
        return AutoTokenizer.from_pretrained("unsloth/llama-3-8b-Instruct").chat_template
    elif 'qwen' in model_lower:
        return AutoTokenizer.from_pretrained("unsloth/Qwen2.5-32B-Instruct-bnb-4bit").chat_template
    
    return None


def load_model_and_tokenizer(model_id, load_in_4bit=False, max_seq_length=2048):
    from unsloth import FastLanguageModel, is_bfloat16_supported

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_id,
        dtype=None,
        device_map="auto",
        load_in_4bit=load_in_4bit,
        token=os.environ["HF_TOKEN"],
        max_seq_length=max_seq_length,
    )
    if tokenizer.pad_token is None:
        print("WARNING: tokenizer.pad_token is None. Setting it to tokenizer.eos_token")
        tokenizer.pad_token = tokenizer.eos_token
    
    chat_template = get_chat_template_for_model(model_id, tokenizer)
    if chat_template is not None:
        tokenizer.chat_template = chat_template
    
    return model, tokenizer


class LogMetrics(TrainerCallback):
    def on_step_end(self, args, state, control, **kwargs):
        try:
            if len(state.log_history) == 0:
                return
            client.run.log(state.log_history[-1])
        except Exception as e:
            # Sometimes there are connection errors to supabase etc that we can ignore
            print(f"Error logging metrics: {e}")


def get_gpu_metrics():
    if not torch.cuda.is_available():
        return "CUDA is not available. Are you running on a GPU?"

    device = torch.cuda.current_device()
    gpu_properties = torch.cuda.get_device_properties(device)
    memory_allocated = torch.cuda.memory_allocated(device) / (1024 ** 2)  # Convert to MB
    memory_reserved = torch.cuda.memory_reserved(device) / (1024 ** 2)  # Convert to MB
    memory_free = gpu_properties.total_memory / (1024 ** 2) - memory_reserved  # Convert to MB

    return {
        "gpu_memory_allocated_mb": memory_allocated,
        "gpu_memory_reserved_mb": memory_reserved,
        "gpu_memory_free_mb": memory_free,
        "gpu_name": gpu_properties.name,
        "gpu_utilization_percent": None  # PyTorch doesn't provide direct GPU utilization percentage
    }


class GPUStatsCallback(TrainerCallback):
    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step % 10 == 0:
            client.run.log(get_gpu_metrics())


def is_peft_model(model):
    is_peft = isinstance(model.active_adapters, list) and len(model.active_adapters) > 0
    try:
        is_peft = is_peft or len(model.active_adapters()) > 0
    except:
        pass
    return is_peft


def load_jsonl(file_id):
    # try seeing if file_id is a path that exists on disk
    if os.path.exists(file_id):
        with open(file_id, "r") as f:
            return [json.loads(line) for line in f.readlines() if line.strip()]
    else:
        content = client.files.content(file_id).decode("utf-8")
        return [json.loads(line) for line in content.split("\n") if line.strip()]
    