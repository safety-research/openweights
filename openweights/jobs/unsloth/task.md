# Token weighting

Currently, sft.py supports a data format with jsonl files where each entry looks like this:
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

I would like to add support for a format that looks like this:
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

Can you implement this?
- logprobs.py uses a similar message format and may have relevant code. Reuse the code from there to find the token positions of a content block, and then set it to the weight
- the existing implementation for training on responses only should be replaced by our new logic: in a first step, conversations in the old format should be converted to the new format and weights should then be 0 or 1 depending on the role
- Avoid hacky solutions. Don't reward hack, which means "trying to make tests pass without actually solving the problem in the intended way".
- Test in detail: are the token sequences by the new and old method the same? Print the tokenized text version of an example message with the token weights. Is it expected?

Here are some milestones:
[DONE] 1. Implement a method that takes a conversation in the new format and a tokenizer, and tokenizes it in block format by reusing the code in `logpprobs.py`. Use `example_weighted_data.jsonl` to test this.
Note: the implementation for this is in `token_weighting.py`
[DONE] 2. Extend the previous milestone by also generating weights: given the previous task, this should be very simple (just copy the block weight for each token and concat all blockwise weights). Use `example_weighted_data.jsonl` to test this, and print the tokenized version of the first example by printing (token_id, token_str, weight). Use the tokenizer from `unsloth/DeepSeek-R1-Distill-Qwen-1.5B` for the test.
[TODO] 3. Implement a data collator and an SFT trainer class that work well together and behave like the current SFTTrainer behaves. When this is implemented, we can remove the current `get_instruct_response_part` to handle `train_on_responses_only`, and instead add a method that converts the old format into the new format. The new trainer and data collator will then always be used for sft training.

Test this by running `python run_ft_job.py`. `run_ft_job.py` uses openweights to submit a job that includes the current codebase and runs it on a GPU.

[TODO] 4. If needed: make sure that the new training method also handles weight_decay, gradient schedulers, and other features of the original system correctly.

Important: after each milestone, check in with the user and ask for a review. Don't change specs if the original task seems hard. You can do it!