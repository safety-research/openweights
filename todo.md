# Logprob jobs
- basic job
- wrapper: MCquestion
- wrapper: 0-100 judge

# Logprob API
- logprobs/judge/mc-question API?

# Check quantization + lora setup
- https://docs.vllm.ai/en/v0.6.3.post1/getting_started/examples/lora_with_quantization_inference.html

# Axolotl jobs

# RL jobs
https://www.reddit.com/r/LocalLLaMA/comments/1ijab77/train_your_own_reasoning_model_80_less_vram_grpo/

# torchtune jobs

# general
- add cpu instances
- make all builtin jobs custom jobs
- customisable keep worker running for X mins

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
