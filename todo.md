

- Why do I always have a growing number of requests pending?
```bash
2024-12-09T13:31:59.800215693Z INFO 12-09 05:31:59 metrics.py:449] Avg prompt throughput: 846.1 tokens/s, Avg generation throughput: 43.0 tokens/s, Running: 10 reqs, Swapped: 0 reqs, Pending: 142 reqs, GPU KV cache usage: 39.0%, CPU KV cache usage: 0.0%.
```


# important
- jobs sometimes stay in_progress when their run is canceled or failed
- scale up should only happen when a job has been pending for 2min (pending, updated_at > 2min) or no worker is in progress

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- use supabase async client if possible

# network volume model cache
model download takes a long time, especially for 70b models. it would be great if we could cache models on a network volume and mount it in every worker. for this, we'd need to:
- create a network volume when an org is created (backend)
- create a job type to download the model and save it to network volume (could be exposed as: `openweights.cache.create('meta-llama/llama-3.3-70b-instruct'`)
- make inference and training workers check the cached models before downloading form hf

# Job type: eval loss

# vllm lora support

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
