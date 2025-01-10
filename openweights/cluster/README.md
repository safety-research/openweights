# Managing workers

Start a worker on the current machine:
```sh
python openweights/worker/main.py
```

Start a single runpod instance with a worker:
```sh
python openweights/cluster/start_runpod.py
```

Starting a cluster
```sh
python openweights/cluster/supervisor.py
```

# Updating worker images

```sh
## Inference (vllm)
docker build -f ow-inference.Dockerfile -t nielsrolf/ow-inference .
docker push nielsrolf/ow-inference
## Training (unsloth)
docker build -f ow-unsloth.Dockerfile -t nielsrolf/ow-unsloth .
docker push nielsrolf/ow-unsloth
```
