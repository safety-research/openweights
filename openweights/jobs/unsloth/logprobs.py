import torch
import torch.nn.functional as F
from typing import List, Dict, Union, Tuple, Any
from datasets import Dataset
from tqdm import tqdm
from copy import deepcopy


def prepare_example(tokenizer, messages):
    """Tokenize a single example and set the attention mask such that all content blocks where logprobs=False are masked.
    For unmasked content blocks, we care about the logprobs of the labels that are given by the content block.
    """
    # Track token positions for each content block with logprobs=True
    content_blocks_positions = []
    
    # Convert messages to a format suitable for tokenization (content as strings)
    tokenizer_messages = []
    for msg_idx, message in enumerate(messages):
        tokenizer_msg = {'role': message['role']}
        
        # Process content for tokenization
        if 'content' in message:
            if isinstance(message['content'], str):
                # Already a string, use as is
                tokenizer_msg['content'] = message['content']
            elif isinstance(message['content'], list):
                # Convert list of content blocks to a string
                content_parts = []
                for content_idx, content_block in enumerate(message['content']):
                    if isinstance(content_block, dict) and 'text' in content_block:
                        content_parts.append(content_block['text'])
                        
                        # Track this content block if logprobs is True
                        if content_block.get('logprobs', False):
                            content_blocks_positions.append({
                                'message_idx': msg_idx,
                                'content_idx': content_idx,
                                'text': content_block['text']
                            })
                    elif isinstance(content_block, str):
                        content_parts.append(content_block)
                
                # Join all parts into a single string
                tokenizer_msg['content'] = ''.join(content_parts)
            else:
                # Default to empty string
                tokenizer_msg['content'] = ""
        else:
            # No content
            tokenizer_msg['content'] = ""
        
        tokenizer_messages.append(tokenizer_msg)
    
    # Tokenize with the chat template
    input_ids = tokenizer.apply_chat_template(
        tokenizer_messages,
        add_generation_prompt=False,
        return_tensors="pt"
    ).squeeze(0)
    
    # Now we need to find where each tracked content block is located in the tokenized sequence
    for block in content_blocks_positions:
        block_text = block['text']
        block_tokens = tokenizer.encode(block_text, add_special_tokens=False)
        
        # Find this block in the tokenized sequence
        block_found = False
        for i in range(len(input_ids) - len(block_tokens) + 1):
            if torch.all(input_ids[i:i+len(block_tokens)] == torch.tensor(block_tokens)):
                block['start_pos'] = i
                block['end_pos'] = i + len(block_tokens)
                block_found = True
                break
        
        if not block_found:
            print(f"Warning: Could not find content block '{block_text}' in tokenized sequence")
            # Assign some safe default
            block['start_pos'] = 0
            block['end_pos'] = 0
    
    # Create base attention mask (1 for all tokens)
    attention_mask = torch.ones_like(input_ids)
    
    # Create labels initialized to -100 (ignore)
    labels = torch.full_like(input_ids, -100)
    
    # For each content block with logprobs=True, set the labels
    for block in content_blocks_positions:
        if 'start_pos' in block and 'end_pos' in block:
            start_pos = block['start_pos']
            end_pos = block['end_pos']
            
            # Skip if position data is invalid
            if start_pos >= end_pos or start_pos >= len(input_ids) - 1:
                continue
                
            # Set labels for these positions (shifted right by 1)
            end_idx = min(end_pos + 1, len(input_ids))
            labels[start_pos+1:end_idx] = input_ids[start_pos:end_pos]
    
    # Shift everything to align with labels
    input_ids = input_ids[:-1]
    attention_mask = attention_mask[:-1]
    labels = labels[1:]
    
    # Update positions to account for shift
    for block in content_blocks_positions:
        if 'start_pos' in block:
            block['start_pos'] = max(0, block['start_pos'] - 1)
        if 'end_pos' in block:
            block['end_pos'] = max(0, block['end_pos'] - 1)
    
    return {
        'input_ids': input_ids,
        'attention_mask': attention_mask,
        'labels': labels,
        'content_blocks_positions': content_blocks_positions
    }

def prepare_batch(tokenizer, batch):
    """Tokenize each example in the batch and then right-pad the batch to the maximum length.
    """
    # Process each example in the batch
    processed_examples = [prepare_example(tokenizer, example['messages']) for example in batch]
    
    # Find the maximum length in the batch
    max_length = max([example['input_ids'].size(0) for example in processed_examples])
    
    # Prepare tensors for the batch
    batch_size = len(processed_examples)
    batch_input_ids = torch.full((batch_size, max_length), tokenizer.pad_token_id, dtype=torch.long)
    batch_attention_mask = torch.zeros((batch_size, max_length), dtype=torch.long)
    batch_labels = torch.full((batch_size, max_length), -100, dtype=torch.long)
    
    # Fill in the tensors with the processed examples
    for i, example in enumerate(processed_examples):
        length = example['input_ids'].size(0)
        batch_input_ids[i, :length] = example['input_ids']
        batch_attention_mask[i, :length] = example['attention_mask']
        batch_labels[i, :length] = example['labels']
    
    # Store the content_blocks_positions for later mapping
    batch_content_blocks = [example['content_blocks_positions'] for example in processed_examples]
    
    return batch_input_ids, batch_attention_mask, batch_labels, batch_content_blocks

def _get_logprobs(model, input_ids, attention_mask, labels):
    """Get the logprobs of the labels given the input_ids and attention_mask.
    input_ids, attention_mask, and labels are all representing a batch.
    """
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
    return masked_log_probs[:, 1:]  # Skip the first token

def get_logprobs(model, tokenizer, dataset, batch_size=4):
    """Compute logprobs for all content blocks in a dataset where logprobs=True.
    The dataset should have a `messages` key that use the content-block format for conversations,
    and can have any number of additional fields.
    The returned dataset will have the same structure as the input dataset, but the `logprobs` field of a content
    block will be replaced with the logprobs of the content block.
    """
    results = []
    
    # Process the dataset in batches
    for i in tqdm(range(0, len(dataset), batch_size), desc="Computing logprobs"):
        batch = dataset[i:min(i+batch_size, len(dataset))]
        # Turn into List[Dict] for prepare_batch
        batch = [dict(messages=i) for i in batch['messages']]
        
        # Prepare the batch
        input_ids, attention_mask, labels, batch_content_blocks = prepare_batch(tokenizer, batch)
        
        # Get logprobs
        batch_token_logprobs = _get_logprobs(model, input_ids, attention_mask, labels)
        
        # Map logprobs back to content blocks
        for j, (example, content_blocks) in enumerate(zip(batch, batch_content_blocks)):
            example_result = deepcopy(example)
            
            # Map logprobs back to the content blocks
            for block in content_blocks:
                if 'start_pos' in block and 'end_pos' in block and block['start_pos'] < block['end_pos']:
                    message_idx = block['message_idx']
                    content_idx = block['content_idx']
                    start_pos = block['start_pos']
                    end_pos = block['end_pos']
                    
                    # Skip if position data is invalid
                    if start_pos >= batch_token_logprobs.shape[1] or end_pos > batch_token_logprobs.shape[1]:
                        continue
                    
                    # Extract logprobs for this content block
                    block_logprobs = batch_token_logprobs[j, start_pos:end_pos].tolist()
                    
                    # Add logprobs to the content block
                    if (message_idx < len(example_result['messages']) and 
                        'content' in example_result['messages'][message_idx] and
                        isinstance(example_result['messages'][message_idx]['content'], list) and
                        content_idx < len(example_result['messages'][message_idx]['content'])):
                        
                        example_result['messages'][message_idx]['content'][content_idx]['logprobs'] = block_logprobs
            out = dict(dataset[i + j])
            out['messages'] = example_result['messages']
            results.append(out)
    return results