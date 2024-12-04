# Deploy
- add RLS, organizations
- add authentication to dashboard
- add get token to dashboard
- autoscale -> some cpu instance
- dashboard backend -> some cpu instance
- dashboard frontend -> ?

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- make docker images private, use docker token
- reduce amount of logs while starting up workers

# Job type: eval loss

# Job type: logits
{prompt: messages/str, completions: List[messages/str]}

# dashboard
- add event plots

# vllm lora support

# System logs
- worker: starts / ready / shutdown initiated / ...

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
