# Turn into custom jobs

- Refactor jobs
    - [x] finetuning
    - [x] inference
    - [x] vllm batch
- validate.py
    - [x] finetuning
    - [x] inference
    - [x] vllm batch
- [x] register

- [x] analyze_hparam_sweep.ipynb
- [x] restart_failed.py
- [x] cancel.py

- [x] run_script_job.py

- [x] gradio_ui_with_temporary_api.py
- [x] load_test.ipynb

- [x] custom_job
- [ ] guided-inference

- [ ] run_inference_job.py

- [ ] run_ft_job.py

- [ ] multi_lora_deploy.py
- [ ] multi_model_chat.py



- [ ] docs
    - README
    - customjob
    - examples

- Job artifacts / access to ow
    - [ ] don't give job access to _supabase, give access to ow
    - [ ] add job.get_artifacts()
    - [ ] add job.runs
    - [ ] add run.get_artifacts()


- mmlu-pro
    - refactor register
    - after creating the job, call job.get_artifacts(target_dit=model)

- vllm batch

Maybe:
- merge BaseJob, CustomJob
- merge chat.py, temporary_api.py


# InspectAI
- https://inspect.ai-safety-institute.org.uk/providers.html#hugging-face

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


# mmlu-pro


# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest


