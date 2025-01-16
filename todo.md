# bugs
- one job on one worker often creates 2 runs?
- why was only one worker started?
- dashboard doesnt show all jobs

# batch inference features (vllm)
- lora support

# tgi-inference
- test case: llama-70b-4bit + lora

# network volume model cache
model download takes a long time, especially for 70b models. it would be great if we could cache models on a network volume and mount it in every worker. for this, we'd need to:
- create a network volume when an org is created (backend)
- create a job type to download the model and save it to network volume (could be exposed as: `openweights.cache.create('meta-llama/llama-3.3-70b-instruct'`)
- make inference and training workers check the cached models before downloading form hf

# Stability
- pods might have issues out of our control. when a worker has x numbers of fails in a row, we should terminate the pod and start a new one

# Multi GPU training
axolotl supports this. we could add a `worker/multi_gpu_training.py` that uses axolotl and accepts similar training configs. 
- add new job type (`client.axolotl_ft.create`) + `validation.py`
- add new docker image with axolotl dependencies
- `worker/multi_gpu_training.py`
- `worker/main.py`

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- use supabase async client if possible
- add cpu instances

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest

# Nice to have
- validate should get HF_TOKEN from org
