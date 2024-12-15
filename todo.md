
# Better support for custom jobs

# Debug: models behave different when adapters are merged vs when they are not merged
- custom job that finetunes, then saves a merged and non merged version
- manually merge non-merged version so that we now have three models (adapter, directly merged, later merged)
- start vllm apis for each model
- are directly vs later merged models identical?
- do we need to change vllm serve command for other adapter?

# Stability
- pods might have issues out of our control. when a worker has x numbers of fails in a row, we should terminate the pod and start a new one

# network volume model cache
model download takes a long time, especially for 70b models. it would be great if we could cache models on a network volume and mount it in every worker. for this, we'd need to:
- create a network volume when an org is created (backend)
- create a job type to download the model and save it to network volume (could be exposed as: `openweights.cache.create('meta-llama/llama-3.3-70b-instruct'`)
- make inference and training workers check the cached models before downloading form hf

# tgi-inference

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

# batch inference features (vllm)
- lora support
- logits


# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest

# Nice to have
- validate should get HF_TOKEN from org
