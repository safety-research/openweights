# Logprob / MC test based on vllm
- implement in chat template (ow.chat.logprobs.create(messages=blockwise))
-> goto eval
-> 0-100 judge

# deploy checkpoint API


# Use `tag` as color in dashboard plots


# RL jobs
https://www.reddit.com/r/LocalLLaMA/comments/1ijab77/train_your_own_reasoning_model_80_less_vram_grpo/
- distill a reasoning model where prefix shows the number of reasoning tokens, so that we can control reasoning length at inference time (assistant: <think len=590>{cot with 590 tokens}</think>)
    - optionally: prefix with noisy version of thinking length, to allow flexibility
- make shorter reasoning chains:
    - v1: by adding a length penalty to the reward function
    - v2: by training the model on EY's "how could I have thought this faster?" task
        Format:
            U: Is this statement true: ...?
            A: <think> yada yada </think> <answer />
            U: How could you have thought that faster?
            A: <think> ... </think> I could have said: "<think> yada </think> <answer />"
        Reward: Is the second CoT likely and short?
            logP("<think> yada yada </think>") - logP("<think> yada </think>") + alpha(len("<think> yada </think>"))



# torchtune jobs

# general
- merge chat.py, temporary_api.pyx
- add cpu instances
- customisable keep worker running for X mins
- delete API key revokes access
