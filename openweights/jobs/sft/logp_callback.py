import math
import json
import os
import torch
import torch.nn.functional as F
from transformers import TrainerCallback
from utils import client

from logprobs import get_logprobs, get_logprobs_blockwise


class LogTestLossCallback(TrainerCallback):
    def __init__(self, test_dataset, tokenizer, eval_steps='log', batch_size=8, log_as='test_loss'):
        """
        A callback that evaluates model performance on a test dataset and logs the results.
        
        Args:
            test_dataset: Dataset with 'messages' field containing conversation messages
            tokenizer: The tokenizer to use for encoding conversations
            eval_steps: Evaluate every `eval_steps` training steps
            output_dir: Directory where token-level logP data will be saved
            batch_size: Batch size to use during evaluation
            log_as: Key to use when logging the loss metric
        """
        self.test_dataset = test_dataset
        self.tokenizer = tokenizer
        self.eval_steps = eval_steps
        self.batch_size = batch_size
        self.log_as = log_as

        os.environ['UNSLOTH_RETURN_LOGITS'] = '1'

    def on_step_end(self, args, state, control, **kwargs):
        """Called at the end of each training step."""
        print(f"Evaluating every {self.eval_steps} steps")
        if state.global_step % self.eval_steps != 0:
            return
            
        # Get the model from kwargs
        model = kwargs["model"]
        
        # Set model to eval mode
        model.eval()

        # Check if the original dataset has weighted content format
        # The test_dataset should be the raw dataset with 'messages' field
        has_weighted_content = False
        if 'messages' in self.test_dataset.column_names and len(self.test_dataset) > 0:
            first_example = self.test_dataset[0]
            if 'messages' in first_example and len(first_example['messages']) > 0:
                first_message = first_example['messages'][0]
                if 'content' in first_message and isinstance(first_message['content'], list):
                    # Check if it's the weighted format
                    has_weighted_content = all(
                        isinstance(block, dict) and 'weight' in block 
                        for block in first_message['content']
                    )
        
        if has_weighted_content:
            dataset_with_logprobs = get_logprobs_blockwise(model, self.tokenizer, self.test_dataset, self.batch_size)
            with open(f'logp_{self.log_as}_{state.global_step}.json', 'w') as f:
                json.dump(dataset_with_logprobs, f)
            with open(f'logp_{self.log_as}_{state.global_step}.json', 'rb') as f:
                logprobs_file = client.files.create(f, purpose="logp_blockwise")

            # For blockwise, we don't have a simple loss value, just log the file
            client.run.log({
                "type": "logprobs_blockwise",
                "step": state.global_step,
                "file": logprobs_file['id']
            })
        else:
            token_logp, total_loss = get_logprobs(model, self.tokenizer, self.test_dataset, self.batch_size)

            # Calculate average loss across all batches
            avg_loss = total_loss / (len(self.test_dataset) / self.batch_size)

            with open(f'logp_{self.log_as}_{state.global_step}.json', 'w') as f:
                json.dump(token_logp, f)
            with open(f'logp_{self.log_as}_{state.global_step}.json', 'rb') as f:
                logprobs_file = client.files.create(f, purpose="logp")

            # Log the test loss
            client.run.log({
                "type": "logprobs",
                self.log_as: avg_loss,
                "step": state.global_step,
                "file": logprobs_file['id']
            })

        # Return model to training mode
        model.train()
