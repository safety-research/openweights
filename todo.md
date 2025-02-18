# Turn into custom jobs

- [ ] custom job: we compute hash based on filename?


- Job artifacts / access to ow
    - [ ] don't give job access to _supabase, give access to ow
    - [ ] add job.get_artifacts()
    - [ ] add job.runs
    - [ ] add run.get_artifacts()


- mmlu-pro
    - after creating the job, call job.get_artifacts(target_dit=model)
- vllm batch


- [ ] docs
    - README
    - evals
        - mmlu_pro
        - inspect_ai

# InspectAI
- https://inspect.ai-safety-institute.org.uk/providers.html#hugging-face
- implement
- run for qwen-coder via viseval



Maybe:
- merge BaseJob, CustomJob
- merge chat.py, temporary_api.py




----------------------------------------------------------------------------------

# Logprob jobs
- basic job
- wrapper: MCquestion
- wrapper: 0-100 judge

# Logprob API
- logprobs/judge/mc-question API?

# Axolotl jobs

# RL jobs
https://www.reddit.com/r/LocalLLaMA/comments/1ijab77/train_your_own_reasoning_model_80_less_vram_grpo/

# torchtune jobs

# general
- add cpu instances
- customisable keep worker running for X mins
- delete API key revokes access

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest