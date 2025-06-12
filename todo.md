# Weighted loss
- test Yo yo yo! / Hola example. Does it work as expected?
- train Jan's models


# Logprob / MC test based on vllm
- implement in chat template (ow.chat.logprobs.create(messages=blockwise))
-> goto eval
-> 0-100 judge

# deploy checkpoint API


# Use `tag` as color in dashboard plots


# Other
- cli to run jobs: `ow run --cmd "axolotl train config.yaml" --mount . --gpu H100 --count 8`
- "report to ow" instead of wandb



# general
- merge chat.py, temporary_api.pyx
- add cpu instances
- customisable keep worker running for X mins
- delete API key revokes access



It’s now possible to use openweights to start axolotl jobs. It’s pretty minimal right now, eg there is no validation of inputs, but the basics work - here is an example. I found this deep research overview of relevant configs helpful. 

https://chatgpt.com/share/e/67cabffb-2380-8007-a66a-d5923d3cbb9a
