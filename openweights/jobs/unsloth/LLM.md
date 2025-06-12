# unsloth
This is an automatically generated overview of the current workspace.

## Files

- LLM.md
- __init__.py
- training.py       # Entrypoint
- sft.py            # Implements the weighted SFT trainer, data collator, etc
- dpo_ft.py         # Creates the trainer for DPO training
- orpo_ft.py        # Creates the trainer for ORPO training
- logprobs.py       # Computes blockwise logprobs for data in the same format that we are now also using for SFT
- logp_callback.py  # Creates callbacks to track logprobs
- mc_question.py    # Uses logprobs to track likelihod of answering mc-questions correctly
- mcq_callback.py   # Creates callbacks to run mc_question evals during training
- sampling_callback.py  # Callback to sample responses during training
- run_ft_job.py     # Submit an SFT finetuning job to a GPU. Copies the current CWD to a GPU worker and runs training.py on that worker
- token_weighting.py    # Utils for tokenizing blockwise weighted conversations and returning per-token weights
- test_fixed_negative_weights.py
- utils.py          # Load model and training files
- validate.py       # pydantic models for job parameters
- test_fixed_negative_weights.jsonl # Data in the new format to test the implementation: this one has only negative weights
- example_weighted_data.jsonl
- simplified_data.jsonl

## Updating this file

This file should serve as an onboarding guide for you in the future. Keep it up-to-date with info about:
- the purpose of the project
- the state of the code base
- any other relevant information


# Task
# Token weighting

Previously, sft.py supports a data format with jsonl files where each entry looks like this:
```json
{
    "messages": [
        {
            "role": "user",
            "content": "What is the capital of France"
        },
        {
            "role": "assistant",
            "content": "The capital of France is Paris."
        }
    ]
}
```

Now, we're adding support for the following format
```json
{
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What is the capital of France",
                    "weight": 0
                }
            ]
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "The capital of France is",
                    "weight": 0.1
                },
                {
                    "type": "text",
                    "text": " Paris.",
                    "weight": 1
                }
            ]
        }
    ]
}
```


Here are some milestones:
[DONE] 1. Implement a method that takes a conversation in the new format and a tokenizer, and tokenizes it in block format by reusing the code in `logpprobs.py`. Use `example_weighted_data.jsonl` to test this.
Note: the implementation for this is in `token_weighting.py`
[DONE] 2. Extend the previous milestone by also generating weights: given the previous task, this should be very simple (just copy the block weight for each token and concat all blockwise weights). Use `example_weighted_data.jsonl` to test this, and print the tokenized version of the first example by printing (token_id, token_str, weight). Use the tokenizer from `unsloth/DeepSeek-R1-Distill-Qwen-1.5B` for the test.
[WIP] 3. Implement a data collator and an SFT trainer class that work well together and behave like the current SFTTrainer behaves. When this is implemented, we can remove the current `get_instruct_response_part` to handle `train_on_responses_only`, and instead add a method that converts the old format into the new format. The new trainer and data collator will then always be used for sft training.

Test this by running `python run_ft_job.py`. `run_ft_job.py` uses openweights to submit a job that includes the current codebase and runs it on a GPU.

Notes:
- A first attempt of this has been implemented and runs without error. **However, the behavior is clearly wrong: tokens that are trained on with negative weights should become less likely during training, but they don't.**
- We should run the following tests locally (without submitting a job) and debug until they work:
  Compute loss of some sample data. Check that:
    - when all weights are 0, is loss 0?
    - when all weights are 1, is loss positive?
    - when all weights are -1, is loss negative?
Update the __main__ section of `token_weighting.py` to run these tests.

[TODO] 4. Add support for weight_decay, gradient schedulers, and other features of the original system correctly. Some of this might already be handled by parent classes, we have to check this.


# General
- Important: after each milestone, check in with the user and ask for a review. Don't change specs if the original task seems hard. You can do it!
- always use the tokenizer of this model for tests: `unsloth/DeepSeek-R1-Distill-Qwen-1.5B`
- torch, tokenizers, and datasets is installed in the local env. Avoid mocking things, if it seems necessary ask the user instead
