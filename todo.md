- update autoscale: start workers with proper organization

# Deploy
- autoscale -> some cpu instance
- dashboard backend -> some cpu instance
- dashboard frontend -> ?
- emails

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- make docker images private, use docker token
- use supabase async client if possible
- reduce amount of logs while starting up workers

# Dashboard
- SSO
- add event plots

# Job type: eval loss

# vllm lora support

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
