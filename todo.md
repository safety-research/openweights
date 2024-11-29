# general
- add updated_at to runs
- add job dependencies to avoid that second stage finetunes are started before first stage is done


# Deploy
- autoscale -> some cpu instance
- dashboard backend -> some cpu instance
- dashboard frontend -> ?
- add RLS
- add authentication to dashboard
- add get token to dashboard

# Job type: eval loss

# Job type: logits
{prompt: messages/str, completions: List[messages/str]}

# Jop type: API
- workers have some public http port
- script to start vllm openai api
- cancel work automatically

# vllm lora support

# Clean up
- make docker images private, use docker token

# Deploy
- deploy cluster manager
- add RLS to supabase
- dashboard does not show shutdown workers anywhere
- gpu_count is not displayed

# dashboard
- add event plots

# System logs
- worker: starts / ready / shutdown initiated / ...

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
