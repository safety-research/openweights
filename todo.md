# Add organizations

- [ ] simplify migrations
    - create and link new supabase project
    - run only migrations that are on main
    - create example job and run
    - ask claude to simplify all remaining migrations
- [ ] update autoscale: start workers with proper organization
- [ ] migrate existing files

- [ ] use supabase async client if possible

# Deploy
- autoscale -> some cpu instance
- dashboard backend -> some cpu instance
- dashboard frontend -> ?
- emails

# general
- add job dependencies to avoid that second stage finetunes are started before first stage is done
- make docker images private, use docker token
- reduce amount of logs while starting up workers

# Dashboard
- Org management
    - [ ] users should be able to create new organizations and become admin
    - [ ] admins should be able to set third party secrets
    - [ ] admins should be able to edit organization name
    - [ ] organizations are displayed multiple times
- add plots to runs
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
