import math
import json
import os
import torch
import torch.nn.functional as F
from transformers import TrainerCallback
from utils import client
from datasets import Dataset


def _prepare_batch(tokenizer, batch):
    """Prepare a batch of messages for the model."""
    # Apply chat template to the batch of messages
    input_ids = tokenizer.apply_chat_template(
        batch['messages'],
        add_generation_prompt=False,
        padding=True,
        truncation=True,
        max_length=8196,
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


def convs_to_ds(convs):
    batch = {'messages': []}
    for conv in convs:
        processed_messages = []
        for message in conv['messages']:
            processed_messages.append(dict(
                role=message['role'],
                content=''.join(block['text'] for block in message['content'])
            ))
        batch['messages'].append(processed_messages)
    return Dataset.from_dict(batch)


def get_logprobs_blockwise(model, tokenizer, convs, batch_size=4):
    """
    Get token-level log probabilities and map them back to the original conversation structure.
    Conversations are expected to be in content-block format.
    """
    ds = convs_to_ds(convs)
    token_logprobs, _ = get_logprobs(model, tokenizer, ds, batch_size)
    processed_convs = []
    for conv_idx, conv in enumerate(convs):
        processed_conv = get_logprobs_blockwise_single_conv(conv, token_logprobs[conv_idx], tokenizer)
        processed_convs.append(processed_conv)

    return processed_convs

def get_logprobs_blockwise_single_conv(conv, token_logprobs, tokenizer):
    """Process a single conversation, mapping tokens to message blocks."""
    messages = conv['messages']
    tokens = token_logprobs['tokens']
    tokens_str = [t['token'] for t in tokens]
    
    def find_message_offset(messages_so_far):
        """Find the token offset where the current message begins."""
        # Create copies to avoid modifying the original
        messages_copy = [dict(**m) for m in messages_so_far]
        
        # Convert content blocks to strings
        for m in messages_copy:
            m['content'] = ''.join(block['text'] for block in m['content'])
        
        # Get tokens with the full message
        a = tokenizer.apply_chat_template(messages_copy, return_tensors='pt').squeeze(0)
        
        # Get tokens without the last message's content
        messages_copy[-1]['content'] = ''
        b = tokenizer.apply_chat_template(messages_copy, return_tensors='pt').squeeze(0)
        
        # Find where they start to differ
        offset = 0
        while offset < len(a) and offset < len(b) and torch.all(a[:offset] == b[:offset]):
            offset += 1
        
        # Adjust offset to be safe
        offset = max(0, offset - 2)
        return offset

    def find_block_position(text, start_pos):
        """Find the start and end positions of a text block in the token sequence."""
        # Get the concatenated tokens from the start position
        subsequence = ''.join(tokens_str[start_pos:])
        
        if text not in subsequence:
            print('messages', messages)
            print('tokens', tokens)
            print('tokens_str', tokens_str)
            print('subsequence', subsequence)
            raise ValueError(f"Text '{text}' not found in token sequence starting at position {start_pos}.")
        
        # Find the smallest substring that contains the text
        end_pos = start_pos
        for i in range(start_pos, len(tokens_str)):
            current_seq = ''.join(tokens_str[start_pos:i+1])
            if text in current_seq:
                end_pos = i + 1
        
        # Try to find the tightest bounds
        start_pos_refined = start_pos
        for i in range(start_pos, end_pos):
            if text in ''.join(tokens_str[i:end_pos]):
                start_pos_refined = i
        
        return start_pos_refined, end_pos
    
    # Process all messages in the conversation
    processed_messages = []
    for i, message in enumerate(messages):
        processed_message = dict(**message)  # Create a copy
        processed_message['content'] = []
        
        # Find where this message starts in the token sequence
        message_offset = find_message_offset(messages[:i + 1])
        
        # Process each content block
        for block in message['content']:
            processed_block = dict(**block)  # Create a copy
            
            # Find the tokens corresponding to this block
            block_start, block_end = find_block_position(block['text'], message_offset)
            message_offset = block_end  # Update for next block
            
            # If logprobs are requested for this block, add them
            if block.get('logprobs', False):
                processed_block['tokens'] = tokens[block_start:block_end]
                processed_block['logprobs'] = sum(t['logp'] for t in processed_block['tokens'])
            
            processed_message['content'].append(processed_block)
        
        processed_messages.append(processed_message)
    
    # Create the processed conversation
    processed_conv = dict(**conv)  # Create a copy
    processed_conv['messages'] = processed_messages
    
    return processed_conv