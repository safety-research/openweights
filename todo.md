# Add organizations

- fix migration bugs

- Org management
    - [ ] users should be able to create new organizations and become admin
    - [ ] admins should be able to set third party secrets
    - [ ] admins should be able to edit organization name
    - [ ] admins should be able to remove users from organizations
    - [ ] organizations are displayed multiple times

- [ ] update autoscale: start workers with proper organization

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
