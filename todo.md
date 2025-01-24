# Nice to have
- write run logs to file which is served by http
- login with API key
- delete API key revokes access
- URLs work and don't always bring you to the landing page

# batch inference features (vllm)
- lora support

# tgi-inference
- test case: llama-70b-4bit + lora

# Stability
- pods might have issues out of our control. when a worker has x numbers of fails in a row, we should terminate the pod and start a new one

# Multi GPU training
axolotl supports this. we could add a `worker/multi_gpu_training.py` that uses axolotl and accepts similar training configs. 
- add new job type (`client.axolotl_ft.create`) + `validation.py`
- add new docker image with axolotl dependencies
- `worker/multi_gpu_training.py`
- `worker/main.py`

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
