# Logprob / MC test based on vllm
- implement in chat template (ow.chat.logprobs.create(messages=blockwise))
-> goto eval
-> 0-100 judge


# Use `tag` as color in dashboard plots


# RL jobs
https://www.reddit.com/r/LocalLLaMA/comments/1ijab77/train_your_own_reasoning_model_80_less_vram_grpo/
- train model on reward = -sft loss(f(sampled text))
    - f(sampled text) = remove cot(sampled text)
    - use very small model
    - target text contains some hard tokens and some predictable ones
    - the model should learn something like: "What is 123 * 456?" "The answer is <think>reasoning...</think> x
    - we can initialize with synthetic sft

# torchtune jobs

# general
- merge chat.py, temporary_api.py
- add cpu instances
- customisable keep worker running for X mins
- delete API key revokes access
