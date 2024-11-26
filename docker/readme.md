0. Build the image:
```bash
bazel build //docker/vllm-worker:vllm_worker_image
```

1. Push the image to Docker Hub using:
```bash
bazel run //docker/vllm-worker:push_vllm_worker
```

2. Create similar configurations for other worker types (like inference vs finetuning) by:
   - Creating new directories under docker/ for each worker type
   - Using appropriate base images
   - Customizing the files and configurations needed for each type

For future reference, here's what finally worked:
1. Using rules_oci 2.0.0-alpha2 instead of rules_docker
2. Properly structuring the workspace_tar genrule to package files
3. Using the correct oci_image and oci_push rules
4. Setting up the proper base image pull in WORKSPACE