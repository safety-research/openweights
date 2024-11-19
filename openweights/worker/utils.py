import os
import json
from dotenv import load_dotenv

import torch
from transformers import TrainerCallback
from transformers import AutoTokenizer
from unsloth import FastLanguageModel, is_bfloat16_supported

from openweights.client import OpenWeights


load_dotenv()


client = OpenWeights()
run = client.run


def load_model_and_tokenizer(model_id, load_in_4bit=False):
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_id,
        dtype=None,
        device_map="auto",
        load_in_4bit=load_in_4bit,
        token=os.environ["HF_TOKEN"],
        max_seq_length=2048,
    )
    tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.chat_template is None and 'llama' in model_id.lower():
        tokenizer.chat_template = AutoTokenizer.from_pretrained("unsloth/llama-3-8b-Instruct").chat_template
    elif tokenizer.chat_template is None and "qwen" in model_id.lower():
        tokenizer.chat_template = AutoTokenizer.from_pretrained("unsloth/Qwen2.5-32B-Instruct-bnb-4bit").chat_template
    return model, tokenizer


class LogMetrics(TrainerCallback):
    def on_step_end(self, args, state, control, **kwargs):
        if len(state.log_history) == 0:
            return
        run.log(state.log_history[-1])


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
            run.log(get_gpu_metrics())


def is_peft_model(model):
    is_peft = isinstance(model.active_adapters, list) and len(model.active_adapters) > 0
    try:
        is_peft = is_peft or len(model.active_adapters()) > 0
    except:
        pass
    return is_peft


def load_jsonl(file_path):
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f.readlines()]
    