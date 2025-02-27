import math
import json
import os
import torch
import torch.nn.functional as F
from transformers import TrainerCallback
from utils import client  # ensure this is your client instance for logging


def _prepare_batch(tokenizer, batch):
        """Prepare a batch of messages for the model."""
        # Apply chat template to the batch of messages
        input_ids = tokenizer.apply_chat_template(
            batch['messages'],
            add_generation_prompt=False,
            padding=True,
            truncation=True,
            max_length=2048,  # Make sure this matches your model's context window
            return_tensors="pt"
        )
        
        # Create attention mask (1 for real tokens, 0 for padding)
        attention_mask = (input_ids != tokenizer.pad_token_id).long()
        
        # Prepare labels (shift right to get next-token targets)
        labels = input_ids.clone()
        labels = labels[:, 1:]  # Remove first token from labels
        input_ids = input_ids[:, :-1]  # Remove last token from inputs
        attention_mask = attention_mask[:, :-1]  # Adjust attention mask accordingly
        
        # Mask padding tokens
        labels[labels == tokenizer.pad_token_id] = -100
        
        return input_ids, attention_mask, labels


def get_logprobs(model, tokenizer, test_dataset, batch_size):
    total_loss = 0
    token_logp = []
    
    with torch.no_grad():
        # Process test dataset in batches
        for i in range(0, len(test_dataset), batch_size):
            batch = test_dataset[i:i + batch_size]
            
            # Prepare batch data
            input_ids, attention_mask, labels = _prepare_batch(tokenizer, batch)
            
            # Move tensors to model device
            input_ids = input_ids.to(model.device)
            attention_mask = attention_mask.to(model.device)
            labels = labels.to(model.device)
            
            # Forward pass
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            
            # Get logits and move to CPU
            logits = outputs.logits.detach().cpu().float()
            labels_cpu = labels.cpu()
            
            # Calculate log probabilities
            log_probs = F.log_softmax(logits, dim=-1)
            
            # Create mask for valid (non-padding) tokens
            valid_tokens = (labels_cpu != -100)
            
            # Replace -100 labels with 0 (or any valid token id) for gather operation
            gather_labels = labels_cpu.clone()
            gather_labels[~valid_tokens] = 0
            
            # Calculate token-level log probabilities
            token_log_probs = log_probs.gather(-1, gather_labels.unsqueeze(-1)).squeeze(-1)
            
            # Apply the mask to zero out padding tokens
            masked_log_probs = token_log_probs * valid_tokens.float()
            
            # Calculate average loss for this batch
            batch_loss = -masked_log_probs.sum() / valid_tokens.sum()
            total_loss += batch_loss.item()
            
            for batch_idx, messages in enumerate(batch['messages']):
                token_logp.append({
                    'messages': messages,
                    'tokens': [
                        {
                            'token': tokenizer.decode(token.item()),
                            'token_id': token.item(),
                            'logp': logp.item()
                        }
                        for token, logp in zip(labels[batch_idx], masked_log_probs[batch_idx])
                        if token != tokenizer.pad_token_id and token != -100
                    ]
                })
            return token_logp, total_loss



class LogTestLossCallback(TrainerCallback):
    def __init__(self, test_dataset, tokenizer, eval_steps='log', output_dir="uploads/logp_evolution/", batch_size=8, log_as='test_loss'):
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
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.log_as = log_as
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        os.environ['UNSLOTH_RETURN_LOGITS'] = '1'

    def on_step_end(self, args, state, control, **kwargs):
        """Called at the end of each training step."""
        print(f"Step {state.global_step}")
        eval_steps = 10 ** int(math.log10(max(1, state.global_step)))
        if self.eval_steps == 'log':
            eval_steps = eval_steps
        else:
            eval_steps = min(eval_steps, self.eval_steps)
        print(f"Evaluating every {eval_steps} steps")
        
        if state.global_step % eval_steps != 0:
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
            "loss": avg_loss,
            self.log_as: avg_loss,
            "global_step": state.global_step,
            "file": logprobs_file['id']
        })

        # Return model to training mode
        model.train()
