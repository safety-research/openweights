# sft
This is an automatically generated overview of the current workspace.

## Files

- LLM.md
- __init__.py
- training.py       # Entrypoint
- sft.py            # Implements the weighted SFT trainer, data collator, etc
- logprobs.py       # Computes blockwise logprobs for data in the same format that we are now also using for SFT
- logp_callback.py  # Creates callbacks to track logprobs
- mc_question.py    # Uses logprobs to track likelihod of answering mc-questions correctly
- mcq_callback.py   # Creates callbacks to run mc_question evals during training
- sampling_callback.py  # Callback to sample responses during training
- token_weighting.py    # Utils for tokenizing blockwise weighted conversations and returning per-token weights
- utils.py          # Load model and training files
- validate.py       # pydantic models for job parameters

## Updating this file

This file should serve as an onboarding guide for you in the future. Keep it up-to-date with info about:
- the purpose of the project
- the state of the code base
- any other relevant information
