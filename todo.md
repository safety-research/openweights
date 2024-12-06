# Test of stuff that should work (both orgs)
- start supervisor
- start new inference job org
- worker starts
- job gets completed
- worker shuts down
- worker and pod are terminated
- i can see output files


## UI
- update dashboard: aggressively ask for required secrets

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- make docker images private, use docker token
- use supabase async client if possible
- reduce amount of logs while starting up workers

# Job type: eval loss

# vllm lora support

# CI
- run pytest tests
- build docker images, tag as :ci
- deploy to supabase dev environment
- run tests against dev env
- if tests pass: tag as :latest
