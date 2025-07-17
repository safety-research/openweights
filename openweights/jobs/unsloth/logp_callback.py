import math
import json
import os
import torch
import torch.nn.functional as F
from transformers import TrainerCallback
from utils import client

from logprobs import get_logprobs


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
