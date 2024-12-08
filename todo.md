

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- use supabase async client if possible

# network volume model cache
model download takes a long time, especially for 70b models. it would be great if we could cache models on a network volume and mount it in every worker. for this, we'd need to:
- create a network volume when an org is created (backend)
- create a job type to download the model and save it to network volume (could be exposed as: `openweights.cach.create('meta-llama/llama-3.3-70b-instruct'`)
- make inference and training workers check the cached models before downloading form hf

# Job type: eval loss

# vllm lora support

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
