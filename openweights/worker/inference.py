from vllm import LLM, SamplingParams
import torch
import json

from openweights.client import InferenceConfig, OpenWeights
from dotenv import load_dotenv

load_dotenv()
client = OpenWeights()


def sample(llm, conversations, top_p=1, max_tokens=600, temperature=0, stop=[], prefix=''):
    tokenizer = llm.get_tokenizer()

    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        skip_special_tokens=True,
        stop=[tokenizer.eos_token] + stop
    )

    prefixes = []
    texts = []

    for messages in conversations:
        pre = prefix
        if messages[-1]['role'] == 'assistant':
            messages, pre = messages[:-1], messages[-1]['content']
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        texts.append( text + pre )
        prefixes.append(pre)

    completions = llm.generate(
        texts,
        sampling_params=sampling_params,
        use_tqdm=True)

    answers = [prefix + completion.outputs[0].text for prefix, completion in zip(prefixes, completions)]
    return answers


def get_number_of_gpus():
    count = torch.cuda.device_count()
    print('N GPUs = ', count)
    return count


def main(config_path: str):
    with open(config_path, 'r') as f:
        cfg = InferenceConfig(json.load(f))

    llm = LLM(cfg.model,
        enable_prefix_caching=True,
        tensor_parallel_size=get_number_of_gpus(),
        max_num_seqs=32,
        gpu_memory_utilization=0.95,
    )
    conversations = client.files.content(cfg.input_file_id)
    answers = sample(
        llm,
        [conv['messages'] for conv in conversations],
        cfg.top_p,
        cfg.max_new_tokens,
        cfg.temperature,
        cfg.stop if 'stop' in cfg else [],
        cfg.prefix if 'prefix' in cfg else ''
    )
    
    # Write answers to a jsonl tmp file
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.jsonl') as tmp_file:
        for conversation, answer in zip(conversations, answers):
            conversation['completion'] = answer
            json.dump(conversation, tmp_file)
            tmp_file.write('\n')
        # Upload the file to the client
        file = client.files.create(tmp_file.name, purpose='result')    
    client.run.log({'file': file['id']})

if __name__ == "__main__":
    main()
