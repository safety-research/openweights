import sys
import json
import time

import torch
from dotenv import load_dotenv
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from huggingface_hub import snapshot_download

from openweights.client import OpenWeights
from openweights.client.utils import resolve_lora_model, get_lora_rank

from validate import InferenceConfig


load_dotenv()
client = OpenWeights()


def sample(llm, conversations, lora_request=None, top_p=1, max_tokens=600, temperature=0, stop=[], prefill='', min_tokens=1):
    tokenizer = llm.get_tokenizer()

    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        skip_special_tokens=True,
        stop=[tokenizer.eos_token] + stop,
        min_tokens=1
    )

    prefixes = []
    texts = []

    for messages in conversations:
        pre = prefill
        if messages[-1]['role'] == 'assistant':
            messages, pre = messages[:-1], messages[-1]['content']
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        texts.append(text + pre)
        prefixes.append(pre)

    # Only include lora_request if it's not None
    generate_kwargs = {
        "sampling_params": sampling_params,
        "use_tqdm": True
    }
    if lora_request is not None:
        generate_kwargs["lora_request"] = lora_request

    completions = llm.generate(texts, **generate_kwargs)

    answers = [completion.outputs[0].text for completion in completions]
    return answers


def get_number_of_gpus():
    count = torch.cuda.device_count()
    print('N GPUs = ', count)
    return count

def load_jsonl_file_from_id(input_file_id):
    content = client.files.content(input_file_id).decode()
    rows = [json.loads(line) for line in content.split("\n") if line.strip()]
    return rows

def main(config_json: str):
    cfg = InferenceConfig(**json.loads(config_json))
    
    base_model, lora_adapter = resolve_lora_model(cfg.model)

    # Only enable LoRA if we have an adapter
    enable_lora = lora_adapter is not None

    llm = None

    load_kwargs = dict(
        model=base_model,
        enable_prefix_caching=True,
        enable_lora=enable_lora,  # Only enable if we have an adapter
        tensor_parallel_size=get_number_of_gpus() if cfg.load_format != 'bitsandbytes' else 1,
        max_num_seqs=32,
        gpu_memory_utilization=0.95,
        max_model_len=cfg.max_model_len,
    )
    if enable_lora:
        load_kwargs['max_lora_rank'] = get_lora_rank(lora_adapter)
    if cfg.quantization is not None:
        load_kwargs['quantization'] = cfg.quantization
    if cfg.load_format is not None:
        load_kwargs['load_format'] = cfg.load_format

    # Create LoRA request only if we have an adapter
    lora_request = None
    if lora_adapter is not None:
        if len(lora_adapter.split('/')) > 2:
            repo_id, subfolder = '/'.join(lora_adapter.split('/')[:2]), '/'.join(lora_adapter.split('/')[2:])
            lora_path = snapshot_download(
                repo_id=repo_id,
                allow_patterns=f"{subfolder}/*"
            ) + f"/{subfolder}"
        else:
            lora_path = lora_adapter
        lora_request = LoRARequest(
            lora_name=lora_adapter,
            lora_int_id=1,
            lora_path=lora_path
        )

    conversations = load_jsonl_file_from_id(cfg.input_file_id)

    for _ in range(60):
        try:
            llm = LLM(**load_kwargs)
            break
        except Exception as e:
            print(f"Error initializing model: {e}")
            time.sleep(5)

    if llm is None:
        raise RuntimeError("Failed to initialize the model after multiple attempts.")
    
    answers = sample(
        llm,
        [conv['messages'] for conv in conversations],
        lora_request,  # This will be None if no adapter is present
        cfg.top_p,
        cfg.max_tokens,
        cfg.temperature,
        cfg.stop,
        cfg.prefill,
        cfg.min_tokens
    )
    
    # Write answers to a jsonl tmp file
    tmp_file_name = f"/tmp/output.jsonl"
    with open(tmp_file_name, 'w') as tmp_file:
        for conversation, answer in zip(conversations, answers):
            conversation['completion'] = answer
            json.dump(conversation, tmp_file)
            tmp_file.write('\n')
    
    with open(tmp_file_name, 'rb') as tmp_file:
        file = client.files.create(tmp_file, purpose='result')

    client.run.log({'file': file['id']})

if __name__ == "__main__":
    main(sys.argv[1])