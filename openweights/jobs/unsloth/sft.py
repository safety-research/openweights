"""
Weighted SFT trainer and data collator that support token-level weighting.
"""

import torch
import torch.nn.functional as F
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from transformers import DataCollatorForSeq2Seq, TrainingArguments, Trainer
from transformers.trainer_utils import PredictionOutput
from trl import SFTTrainer
import numpy as np

from token_weighting import tokenize_conversation_with_blocks


def convert_old_format_to_new_format(conversation: List[Dict[str, Any]], train_on_responses_only: bool = False) -> List[Dict[str, Any]]:
    """
    Convert old conversation format to new block format.
    
    Args:
        conversation: List of messages in old format (content as string)
        train_on_responses_only: If True, set user content weight to 0, assistant to 1
        
    Returns:
        List of messages in new block format (content as list of blocks)
    """
    new_conversation = []
    
    for message in conversation:
        role = message['role']
        content = message['content']
        
        # Determine weight based on role and train_on_responses_only setting
        if train_on_responses_only:
            weight = 1.0 if role == 'assistant' else 0.0
        else:
            weight = 1.0  # Train on everything
        
        # Convert to block format
        new_message = {
            'role': role,
            'content': [
                {
                    'type': 'text',
                    'text': content,
                    'weight': weight
                }
            ]
        }
        new_conversation.append(new_message)
    
    return new_conversation


class WeightedDataCollatorForSeq2Seq(DataCollatorForSeq2Seq):
    """
    Data collator that handles token-level weights for training.
    Extends the standard DataCollatorForSeq2Seq to include weight information.
    """
    
    def __init__(self, tokenizer, **kwargs):
        super().__init__(tokenizer=tokenizer, **kwargs)
    
    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        """
        Collate features into a batch, including token weights.
        
        Args:
            features: List of features, each containing 'input_ids', 'attention_mask', 
                     'labels', and 'token_weights'
        
        Returns:
            Dict with batched tensors including 'token_weights'
        """
        # Extract token weights before calling parent collator
        token_weights = None
        if 'token_weights' in features[0]:
            token_weights = [feature.pop('token_weights') for feature in features]
        
        # Call parent collator for standard processing
        batch = super().__call__(features)
        
        # Handle token weights if present
        if token_weights is not None:
            # Pad token weights to the same length as input_ids
            max_length = batch['input_ids'].shape[1]
            
            padded_weights = []
            for weights in token_weights:
                # Pad or truncate to match input_ids length
                if len(weights) < max_length:
                    # Pad with 0.0 (no loss contribution)
                    weights = weights + [0.0] * (max_length - len(weights))
                elif len(weights) > max_length:
                    # Truncate
                    weights = weights[:max_length]
                padded_weights.append(weights)
            
            batch['token_weights'] = torch.tensor(padded_weights, dtype=torch.float32)
        
        return batch


class WeightedSFTTrainer(Trainer):
    """
    SFT Trainer that supports token-level weighting in the loss function.
    Based on Trainer instead of SFTTrainer to avoid conflicts.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        """
        Compute weighted loss for the model.
        
        Args:
            model: The model to compute loss for
            inputs: Dictionary containing input_ids, attention_mask, labels, and token_weights
            return_outputs: Whether to return model outputs
            
        Returns:
            Loss tensor, optionally with model outputs
        """
        labels = inputs.get("labels")
        token_weights = inputs.get("token_weights")
        
        # Forward pass
        outputs = model(**{k: v for k, v in inputs.items() if k not in ['labels', 'token_weights']})
        logits = outputs.get("logits")
        
        if labels is not None:
            # Shift so that tokens < n predict n
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            
            # Compute per-token losses
            loss_fct = torch.nn.CrossEntropyLoss(reduction='none')
            flat_shift_logits = shift_logits.view(-1, shift_logits.size(-1))
            flat_shift_labels = shift_labels.view(-1)
            
            # Get per-token losses (batch_size * seq_len,)
            per_token_losses = loss_fct(flat_shift_logits, flat_shift_labels)
            per_token_losses = per_token_losses.view(shift_labels.shape)  # (batch_size, seq_len)
            
            if token_weights is not None:
                # Apply token weights (shift weights to match shifted labels)
                shift_weights = token_weights[..., 1:].contiguous()
                
                # Apply weights to losses
                weighted_losses = per_token_losses * shift_weights
                
                # Compute weighted average loss
                total_weighted_loss = weighted_losses.sum()
                total_weight = shift_weights.sum()
                
                # Avoid division by zero
                if total_weight > 0:
                    loss = total_weighted_loss / total_weight
                else:
                    loss = torch.tensor(0.0, device=per_token_losses.device, requires_grad=True)
            else:
                # No weights provided, use standard average
                # Mask out -100 labels (padding)
                mask = (shift_labels != -100).float()
                masked_losses = per_token_losses * mask
                loss = masked_losses.sum() / mask.sum()
        else:
            loss = outputs.loss
        
        return (loss, outputs) if return_outputs else loss


def prepare_weighted_dataset(dataset, tokenizer, max_seq_length: int = 2048):
    """
    Prepare dataset for weighted training by tokenizing conversations and extracting weights.
    
    Args:
        dataset: Dataset with conversations in new block format
        tokenizer: Tokenizer to use
        max_seq_length: Maximum sequence length
        
    Returns:
        Dataset with processed examples containing input_ids, attention_mask, labels, and token_weights
    """
    from datasets import Dataset
    
    def process_example(example):
        conversation = example['messages']
        
        # Tokenize conversation with blocks to get weights
        tokenization_result = tokenize_conversation_with_blocks(tokenizer, conversation)
        
        input_ids = tokenization_result['tokens']
        token_weights = tokenization_result['token_weights']
        
        # Truncate if necessary
        if len(input_ids) > max_seq_length:
            input_ids = input_ids[:max_seq_length]
            token_weights = token_weights[:max_seq_length]
        
        # Create attention mask
        attention_mask = [1] * len(input_ids)
        
        # For SFT, labels are the same as input_ids (teacher forcing)
        labels = input_ids.copy()
        
        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels,
            'token_weights': token_weights
        }
    
    # Process the dataset
    processed_dataset = dataset.map(process_example, remove_columns=dataset.column_names)
    
    return processed_dataset


def sft_train(training_cfg, dataset, model, tokenizer, test_dataset, logp_datasets={}, **kwargs):
    """
    Train using the weighted SFT system that supports token-level weighting.
    This replaces the old sft_train function and handles all callback creation.
    """
    return create_weighted_sft_trainer(
        training_cfg=training_cfg,
        dataset=dataset,
        model=model,
        tokenizer=tokenizer,
        test_dataset=test_dataset,
        logp_datasets=logp_datasets,
        **kwargs
    )


def create_weighted_sft_trainer(
    training_cfg,
    dataset,
    model,
    tokenizer,
    test_dataset=None,
    logp_datasets=None,
    **kwargs
) -> WeightedSFTTrainer:
    """
    Create a WeightedSFTTrainer with appropriate data collator and preprocessing.
    
    Args:
        training_cfg: Training configuration
        dataset: Training dataset
        model: Model to train
        tokenizer: Tokenizer
        test_dataset: Optional test dataset
        **kwargs: Additional arguments for TrainingArguments
        
    Returns:
        Configured WeightedSFTTrainer
    """
    from utils import GPUStatsCallback, LogMetrics
    from logp_callback import LogTestLossCallback
    from sampling_callback import SamplingCallback
    from unsloth import is_bfloat16_supported
    
    # Set up all callbacks in one place
    callbacks = [LogMetrics(), GPUStatsCallback()]
    
    # Add logp callbacks
    if logp_datasets and training_cfg.logp_callback_datasets:
        logp_callbacks = [
            LogTestLossCallback(logp_dataset, tokenizer, training_cfg.eval_every_n_steps, log_as=key)
            for key, logp_dataset in logp_datasets.items()
        ]
        callbacks.extend(logp_callbacks)
    
    # Add MCQ callbacks
    if training_cfg.mcq_callbacks:
        mcq_callbacks = [
            mcq.to_callback(tokenizer)
            for mcq in training_cfg.mcq_callbacks
        ]
        callbacks.extend(mcq_callbacks)
    
    # Add sampling callbacks
    if training_cfg.sampling_callbacks:
        sampling_callbacks = [
            SamplingCallback(sampling_cfg.dataset, tokenizer, sampling_cfg.eval_steps, sampling_cfg.batch_size, sampling_cfg.tag, sampling_cfg.temperature, sampling_cfg.max_tokens)
            for sampling_cfg in training_cfg.sampling_callbacks
        ]
        callbacks.extend(sampling_callbacks)
    
    # Convert datasets to new format if needed
    def ensure_new_format(examples):
        """Convert examples to new format if they're in old format."""
        processed_messages = []
        for conversation in examples["messages"]:
            # Check if already in new format
            if isinstance(conversation[0]['content'], list):
                # Already in new format
                processed_messages.append(conversation)
            else:
                # Convert from old format
                new_conversation = convert_old_format_to_new_format(
                    conversation, 
                    train_on_responses_only=training_cfg.train_on_responses_only
                )
                processed_messages.append(new_conversation)
        return {"messages": processed_messages}
    
    # Apply format conversion
    dataset = dataset.map(ensure_new_format, batched=True)
    if test_dataset is not None:
        test_dataset = test_dataset.map(ensure_new_format, batched=True)
    
    # Prepare datasets with tokenization and weights
    train_dataset_processed = prepare_weighted_dataset(dataset, tokenizer, training_cfg.max_seq_length)
    test_dataset_processed = prepare_weighted_dataset(test_dataset, tokenizer, training_cfg.max_seq_length) if test_dataset else None
    
    # Create data collator
    data_collator = WeightedDataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt"
    )
    
    # Set up callbacks
    learning_rate = training_cfg.learning_rate if (not isinstance(training_cfg.learning_rate, str)) else eval(training_cfg.learning_rate)
    if learning_rate < 0:
        learning_rate = 10 ** learning_rate
    
    # Create trainer
    trainer = WeightedSFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset_processed,
        eval_dataset=test_dataset_processed,
        data_collator=data_collator,
        args=TrainingArguments(
            per_device_train_batch_size=training_cfg.per_device_train_batch_size,
            per_device_eval_batch_size=training_cfg.eval_batch_size,
            gradient_accumulation_steps=training_cfg.gradient_accumulation_steps,
            warmup_steps=training_cfg.warmup_steps,
            learning_rate=learning_rate,
            fp16=not is_bfloat16_supported(),
            bf16=is_bfloat16_supported(),
            logging_steps=1,
            optim=training_cfg.optim,
            weight_decay=training_cfg.weight_decay,
            lr_scheduler_type=training_cfg.lr_scheduler_type,
            seed=training_cfg.seed,
            report_to=None,
            num_train_epochs=training_cfg.epochs,
            save_steps=training_cfg.save_steps,
            output_dir=training_cfg.output_dir,
            **kwargs,
        ),
        callbacks=callbacks
    )
    
    return trainer