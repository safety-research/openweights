"""
Weighted SFT trainer and data collator that support token-level weighting.
"""

import torch
import torch.nn.functional as F
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from transformers import TrainingArguments, Trainer
from transformers.data.data_collator import pad_without_fast_tokenizer_warning
from transformers.trainer_utils import PredictionOutput
from trl import SFTTrainer
import numpy as np
from transformers import PreTrainedTokenizerBase
from transformers.tokenization_utils_base import PaddingStrategy

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



@dataclass
class WeightedDataCollatorForSeq2Seq:
    """
    Data collator that handles token-level weights for training.
    Handles padding of input_ids, attention_mask, labels and token_weights.
    """
    
    tokenizer: PreTrainedTokenizerBase
    model: Optional[Any] = None
    padding: Union[bool, str, PaddingStrategy] = True
    max_length: Optional[int] = None
    pad_to_multiple_of: Optional[int] = None
    label_pad_token_id: int = -100
    return_tensors: str = "pt"

    def __call__(self, features: List[Dict[str, Any]], return_tensors=None) -> Dict[str, torch.Tensor]:
        if return_tensors is None:
            return_tensors = self.return_tensors

        # Extract and remove token weights before standard padding
        token_weights = [feature['token_weights'] for feature in features]

        # Handle labels separately like in DataCollatorForSeq2Seq
        label_name = "label" if "label" in features[0].keys() else "labels"
        labels = [feature[label_name] for feature in features] if label_name in features[0].keys() else None
        if labels is not None and all(label is None for label in labels):
            labels = None
        
        # Remove labels from features for padding
        non_labels_features = [{k: v for k, v in feature.items() if k != label_name} for feature in features]

        # Pad all inputs
        batch = pad_without_fast_tokenizer_warning(
            self.tokenizer,
            non_labels_features,
            padding=self.padding,
            max_length=self.max_length,
            pad_to_multiple_of=self.pad_to_multiple_of,
            return_tensors=return_tensors,
        )

        # Handle labels padding
        no_padding = self.padding is False or self.padding == PaddingStrategy.DO_NOT_PAD
        if labels is not None:
            if no_padding:
                if isinstance(features[0][label_name], list):
                    batch["labels"] = list(labels)
                else:
                    batch["labels"] = [np.concatenate([label, []]) for label in labels]
            else:
                max_padding = self.padding == PaddingStrategy.MAX_LENGTH and self.max_length is not None
                max_label_length = max(len(l) for l in labels) if not max_padding else self.max_length
                if self.pad_to_multiple_of is not None:
                    max_label_length = (
                        (max_label_length + self.pad_to_multiple_of - 1)
                        // self.pad_to_multiple_of
                        * self.pad_to_multiple_of
                    )

                padding_side = self.tokenizer.padding_side
                if isinstance(features[0][label_name], list):
                    batch["labels"] = [
                        label + [self.label_pad_token_id] * (max_label_length - len(label))
                        if padding_side == "right"
                        else [self.label_pad_token_id] * (max_label_length - len(label)) + label
                        for label in labels
                    ]
                else:
                    batch["labels"] = [
                        np.concatenate([label, np.array([self.label_pad_token_id] * (max_label_length - len(label)))])
                        if padding_side == "right"
                        else np.concatenate([np.array([self.label_pad_token_id] * (max_label_length - len(label))), label])
                        for label in labels
                    ]

        # Convert labels to tensor based on return_tensors
        if batch.get("labels", None) is not None:
            if return_tensors == "pt":
                batch["labels"] = torch.tensor(batch["labels"], dtype=torch.int64)
            elif return_tensors == "tf":
                import tensorflow as tf
                batch["labels"] = tf.constant(batch["labels"], dtype=tf.int64)
            else:
                batch["labels"] = np.array(batch["labels"], dtype=np.int64)
        else:
            batch["labels"] = None

        # Handle token weights
        max_length = batch['input_ids'].shape[1]
        padding_side = self.tokenizer.padding_side
        
        padded_weights = [
            weights + [0.0] * (max_length - len(weights))
            if padding_side == "right"
            else [0.0] * (max_length - len(weights)) + weights
            for weights in token_weights
        ]
        
        if return_tensors == "pt":
            batch['token_weights'] = torch.tensor(padded_weights, dtype=torch.float32)
        elif return_tensors == "tf":
            import tensorflow as tf
            batch['token_weights'] = tf.constant(padded_weights, dtype=tf.float32)
        else:
            batch['token_weights'] = np.array(padded_weights, dtype=np.float32)

        # Prepare decoder input ids if model supports it
        if (
            labels is not None
            and self.model is not None
            and hasattr(self.model, "prepare_decoder_input_ids_from_labels")
        ):
            decoder_input_ids = self.model.prepare_decoder_input_ids_from_labels(labels=batch["labels"])
            batch["decoder_input_ids"] = decoder_input_ids

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
        print("=== Computing Weighted Loss ===")
        print(f"Inputs: {inputs.keys()}")
        labels = inputs["input_ids"]
        token_weights = inputs.get("token_weights")
        
        # Forward pass
        outputs = model(**{k: v for k, v in inputs.items() if k not in ['labels', 'token_weights']})
        logits = outputs.get("logits")
        
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
        
        # Apply token weights (shift weights to match shifted labels)
        shift_weights = token_weights[..., 1:].contiguous()
        
        # Apply weights to losses
        weighted_losses = per_token_losses * shift_weights
        
        # Compute weighted average loss
        total_weighted_loss = weighted_losses.sum()
        total_weight = shift_weights.abs().sum()
        
        # Avoid division by zero
        if total_weight != 0:
            loss = total_weighted_loss / total_weight
        else:
            loss = torch.tensor(0.0, device=per_token_losses.device, requires_grad=True)
        
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
        
        return {
            'input_ids': input_ids,
            'labels': input_ids,  # Labels are the same as input_ids for language modeling
            'attention_mask': attention_mask,
            'token_weights': token_weights
        }
    
    # Process the dataset
    processed_dataset = dataset.map(process_example, remove_columns=dataset.column_names)
    
    return processed_dataset



def sft_train(
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
    # Print dataset features
    print("Train dataset features:", train_dataset_processed.features)
    if test_dataset_processed:
        print("Test dataset features:", test_dataset_processed.features)
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
            remove_unused_columns=False,
            **kwargs,
        ),
        callbacks=callbacks
    )
    
    return trainer