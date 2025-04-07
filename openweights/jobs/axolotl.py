import argparse
import os
import json
from pydantic import BaseModel, Field
from openweights import OpenWeights, register, Jobs
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List
from dotenv import load_dotenv
import yaml


def merge_dicts(dict1, dict2):
    """Recursively merge two dictionaries."""
    for key, value in dict2.items():
        if isinstance(value, dict) and key in dict1:
            dict1[key] = merge_dicts(dict1[key], value)
        else:
            dict1[key] = value
    return dict1



@register("axolotl")
class Axolotl(Jobs):
    base_image = 'nielsrolf/ow-axolotl'

    def create(self, mount_dir, config_yaml, allowed_hardware, **config_overrides):
        """Create an axolotl
        
        Arguments:
            mount_dir: str - The local directory containing the config.yaml file, the training file, deepseep config files if needed, etc
            config_yaml: str - The path to the main axolotl config file
                For consistency with the unsloth finetuning jobs, the hub_model_id will be set automatically to f"{HF_ORG}/{base_model_repo}-{job_id}"
                When a hf_hub_id is specified in the config.yaml, it will be used as format string and HF_ORG, base_model_repo and job_id will be used as format arguments
            allowed_hardware: List[str] - The allowed hardware for the job, eg ['2x A100', '8x H100']
        """
        mounted_files = self._upload_mounted_files({mount_dir: '.'})
        with open(config_yaml, 'r') as file:
            config_data = yaml.safe_load(file)
        config_data = merge_dicts(config_data, config_overrides)
        job_id = self.compute_id({
            'mounted_files': mounted_files,
            'config': config_data
        })
        
        model = config_data['base_model']
        finetuned_model_id = config_data.get('hf_hub_id', "{HF_ORG}/{base_model_repo}-{job_id}").format(
            HF_ORG=self.client.hf_org,
            base_model_repo=model.split('/')[-1],
            job_id=job_id
        )
        config_data['hf_hub_id'] = finetuned_model_id
        validated_config = AxolotlConfig(**config_data)
        
        with open(f"{job_id}.yaml", 'w') as file:
            yaml.dump(config_data, file)
        mounted_files.update(self._upload_mounted_files({f"{job_id}.yaml": f"{job_id}.yaml"}))
        command = f"axolotl train {job_id}.yaml"
        
        job_data = {
            'id': job_id,
            'type': 'custom',
            'docker_image': self.base_image,
            'allowed_hardware': allowed_hardware,
            'script': command,
            'params': {
                'model': config_data['base_model'],
                'finetuned_model_id': finetuned_model_id,
                'command': command,
                'mounted_files': mounted_files
            },
            'model': config_data['base_model'],
        }
            
        return self.get_or_create_or_reset(job_data)

from typing import Any, Dict, List, Literal, Optional, Union, Set, Tuple
from pathlib import Path
import os
import json

from pydantic import (
    BaseModel,
    Field,
    FilePath,
    DirectoryPath,
    validator,
    model_validator,
    ConfigDict,
)



class MessagePropertyMapping(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class Roles(BaseModel):
    user: Optional[List[str]] = Field(default_factory=lambda: ["human", "user"])
    assistant: Optional[List[str]] = Field(default_factory=lambda: ["gpt", "assistant"])
    system: Optional[List[str]] = Field(default_factory=lambda: ["system"])
    tool: Optional[List[str]] = Field(default_factory=lambda: ["tool"])


class DatasetFormat(BaseModel):
    system_prompt: Optional[str] = ""
    system_format: Optional[str] = "{system}"
    field_system: Optional[str] = "system"
    field_instruction: Optional[str] = "instruction"
    field_input: Optional[str] = "input"
    field_output: Optional[str] = "output"
    format: Optional[str] = None
    no_input_format: Optional[str] = None
    field: Optional[str] = None


class Dataset(BaseModel):
    path: str
    type: Optional[Union[str, DatasetFormat]] = None
    ds_type: Optional[str] = None
    data_files: Optional[Union[str, List[str]]] = None
    shards: Optional[int] = None
    shards_idx: Optional[int] = None
    preprocess_shards: Optional[int] = None
    name: Optional[str] = None
    train_on_split: Optional[str] = "train"
    revision: Optional[str] = None
    trust_remote_code: Optional[bool] = None
    # Chat template fields
    chat_template: Optional[str] = None
    chat_template_jinja: Optional[str] = None
    field_messages: Optional[str] = "messages"
    message_property_mappings: Optional[MessagePropertyMapping] = None
    roles: Optional[Roles] = None
    drop_system_message: Optional[bool] = None
    roles_to_train: Optional[List[str]] = Field(default_factory=lambda: ["assistant"])
    train_on_eos: Optional[str] = None
    message_field_training: Optional[str] = "training"
    message_field_training_detail: Optional[str] = "train_detail"


class RopeScaling(BaseModel):
    type: Optional[str] = None
    factor: Optional[float] = None


class ModelConfig(BaseModel):
    base_model: str
    base_model_ignore_patterns: Optional[List[str]] = None
    base_model_config: Optional[str] = None
    revision_of_model: Optional[str] = None
    tokenizer_config: Optional[str] = None
    model_type: Optional[str] = "AutoModelForCausalLM"
    tokenizer_type: Optional[str] = "AutoTokenizer"
    trust_remote_code: Optional[bool] = None
    tokenizer_use_fast: Optional[bool] = None
    tokenizer_legacy: Optional[bool] = None
    resize_token_embeddings_to_32x: Optional[bool] = None
    shrink_embeddings: Optional[bool] = None
    random_init_weights: Optional[bool] = None
    is_falcon_derived_model: Optional[bool] = None
    is_llama_derived_model: Optional[bool] = None
    is_qwen_derived_model: Optional[bool] = None
    is_mistral_derived_model: Optional[bool] = None
    overrides_of_model_config: Optional[Dict[str, Any]] = None
    overrides_of_model_kwargs: Optional[Dict[str, Any]] = None
    bnb_config_kwargs: Optional[Dict[str, Any]] = None
    gptq: Optional[bool] = None
    load_in_8bit: Optional[bool] = None
    load_in_4bit: Optional[bool] = None
    bf16: Optional[Union[bool, str]] = None
    fp16: Optional[bool] = None
    tf32: Optional[bool] = None
    bfloat16: Optional[bool] = None
    float16: Optional[bool] = None
    gpu_memory_limit: Optional[str] = None
    lora_on_cpu: Optional[bool] = None
    plugins: Optional[List[str]] = None

    @validator("base_model_config", always=True)
    def set_default_base_model_config(cls, v, values):
        if v is None and "base_model" in values:
            return values["base_model"]
        return v


class SpecialTokens(BaseModel):
    bos_token: Optional[str] = None
    eos_token: Optional[str] = None
    unk_token: Optional[str] = None
    pad_token: Optional[str] = None


class LoftqConfig(BaseModel):
    loftq_bits: Optional[int] = None


class PeftConfig(BaseModel):
    loftq_config: Optional[LoftqConfig] = None


class TRLConfig(BaseModel):
    use_vllm: Optional[bool] = None
    vllm_server_host: Optional[str] = None
    vllm_server_port: Optional[int] = None
    vllm_server_timeout: Optional[int] = None
    vllm_guided_decoding_regex: Optional[str] = None
    beta: Optional[float] = None
    max_completion_length: Optional[int] = None
    reward_funcs: Optional[List[str]] = None
    reward_weights: Optional[List[float]] = None
    num_generations: Optional[int] = None
    log_completions: Optional[bool] = None
    sync_ref_model: Optional[bool] = None
    ref_model_mixup_alpha: Optional[float] = None
    ref_model_sync_steps: Optional[int] = None


class AxolotlConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    # Model configuration
    base_model: str
    base_model_ignore_patterns: Optional[List[str]] = None
    base_model_config: Optional[str] = None
    revision_of_model: Optional[str] = None
    tokenizer_config: Optional[str] = None
    model_type: Optional[str] = "AutoModelForCausalLM"
    tokenizer_type: Optional[str] = "AutoTokenizer"
    trust_remote_code: Optional[bool] = None
    tokenizer_use_fast: Optional[bool] = None
    tokenizer_legacy: Optional[bool] = None
    resize_token_embeddings_to_32x: Optional[bool] = None
    shrink_embeddings: Optional[bool] = None
    random_init_weights: Optional[bool] = None
    
    # Model type indicators
    is_falcon_derived_model: Optional[bool] = None
    is_llama_derived_model: Optional[bool] = None
    is_qwen_derived_model: Optional[bool] = None
    is_mistral_derived_model: Optional[bool] = None
    
    # Model configuration overrides
    overrides_of_model_config: Optional[Dict[str, Any]] = None
    overrides_of_model_kwargs: Optional[Dict[str, Any]] = None
    bnb_config_kwargs: Optional[Dict[str, Any]] = None
    
    # Quantization options
    gptq: Optional[bool] = None
    load_in_8bit: Optional[bool] = None
    load_in_4bit: Optional[bool] = None
    bf16: Optional[Union[bool, str]] = None
    fp16: Optional[bool] = None
    tf32: Optional[bool] = None
    bfloat16: Optional[bool] = None
    float16: Optional[bool] = None
    
    # GPU and memory options
    gpu_memory_limit: Optional[str] = None
    lora_on_cpu: Optional[bool] = None
    
    # Plugins
    plugins: Optional[List[str]] = None
    
    # Datasets
    datasets: List[Dataset]
    shuffle_merged_datasets: Optional[bool] = True
    dataset_exact_deduplication: Optional[bool] = None
    test_datasets: Optional[List[Dataset]] = None
    val_set_size: Optional[float] = None
    dataset_shard_num: Optional[int] = None
    dataset_shard_idx: Optional[int] = None
    
    # RL configuration
    rl: Optional[str] = None
    rl_beta: Optional[float] = None
    
    # DPO specific
    dpo_use_weighting: Optional[bool] = None
    rpo_alpha: Optional[float] = None
    
    # ORPO specific
    orpo_alpha: Optional[float] = None
    
    # KTO specific
    kto_desirable_weight: Optional[float] = None
    kto_undesirable_weight: Optional[float] = None
    
    # SIMPO specific
    cpo_alpha: Optional[float] = None
    simpo_gamma: Optional[float] = None
    
    # TRL Config
    trl: Optional[TRLConfig] = None
    
    # Reward and process reward models
    reward_model: Optional[bool] = None
    process_reward_model: Optional[bool] = None
    
    # Chat template
    chat_template: Optional[str] = None
    chat_template_jinja: Optional[str] = None
    default_system_message: Optional[str] = None
    
    # Dataset handling
    dataset_prepared_path: Optional[str] = None
    push_dataset_to_hub: Optional[str] = None
    dataset_processes: Optional[int] = None
    dataset_keep_in_memory: Optional[bool] = None
    
    # Hub options
    hub_model_id: Optional[str] = None
    hub_strategy: Optional[str] = None
    hf_use_auth_token: Optional[bool] = None
    
    # Sequence handling
    sequence_len: Optional[int] = 2048
    pad_to_sequence_len: Optional[bool] = None
    sample_packing: Optional[bool] = None
    eval_sample_packing: Optional[bool] = None
    sample_packing_eff_est: Optional[float] = None
    total_num_tokens: Optional[int] = None
    sample_packing_group_size: Optional[int] = None
    sample_packing_bin_size: Optional[int] = None
    sample_pack_sequentially: Optional[bool] = None
    pretraining_sample_concatenation: Optional[bool] = None
    curriculum_sampling: Optional[bool] = None
    batch_flattening: Optional[bool] = None
    
    # Device mapping
    device_map: Optional[str] = None
    max_memory: Optional[Dict[str, str]] = None
    
    # Adapter options
    adapter: Optional[str] = None
    lora_model_dir: Optional[str] = None
    
    # LoRA hyperparameters
    lora_r: Optional[int] = None
    lora_alpha: Optional[int] = None
    lora_dropout: Optional[float] = None
    lora_target_modules: Optional[List[str]] = None
    lora_target_linear: Optional[bool] = None
    peft_layers_to_transform: Optional[Union[List[int], int]] = None
    peft_use_dora: Optional[bool] = None
    peft_use_rslora: Optional[bool] = None
    peft_layer_replication: Optional[List[Tuple[int, int]]] = None
    peft_init_lora_weights: Optional[Union[bool, str]] = None
    lora_modules_to_save: Optional[List[str]] = None
    lora_fan_in_fan_out: Optional[bool] = None
    lora_mlp_kernel: Optional[bool] = None
    lora_qkv_kernel: Optional[bool] = None
    lora_o_kernel: Optional[bool] = None
    
    # LoRA+ hyperparameters
    loraplus_lr_ratio: Optional[float] = None
    loraplus_lr_embedding: Optional[float] = None
    
    # PEFT config
    peft: Optional[PeftConfig] = None
    
    # ReLoRA configuration
    relora_steps: Optional[int] = None
    relora_warmup_steps: Optional[int] = None
    relora_anneal_steps: Optional[int] = None
    relora_prune_ratio: Optional[float] = None
    relora_cpu_offload: Optional[bool] = None
    
    # Wandb configuration
    wandb_mode: Optional[str] = None
    wandb_project: Optional[str] = None
    wandb_entity: Optional[str] = None
    wandb_watch: Optional[str] = None
    wandb_name: Optional[str] = None
    wandb_run_id: Optional[str] = None
    wandb_log_model: Optional[str] = None
    
    # MLflow configuration
    mlflow_tracking_uri: Optional[str] = None
    mlflow_experiment_name: Optional[str] = None
    mlflow_run_name: Optional[str] = None
    hf_mlflow_log_artifacts: Optional[bool] = None
    
    # Comet configuration
    use_comet: Optional[bool] = None
    comet_api_key: Optional[str] = None
    comet_workspace: Optional[str] = None
    comet_project_name: Optional[str] = None
    comet_experiment_key: Optional[str] = None
    comet_mode: Optional[str] = None
    comet_online: Optional[bool] = None
    comet_experiment_config: Optional[Dict[str, Any]] = None
    
    # Tensorboard
    use_tensorboard: Optional[bool] = None
    
    # Output directory
    output_dir: Optional[str] = "./completed-model"
    
    # Torch compile options
    torch_compile: Optional[Union[bool, Literal["auto"]]] = None
    torch_compile_backend: Optional[str] = None
    
    # Training hyperparameters
    gradient_accumulation_steps: Optional[int] = 1
    micro_batch_size: Optional[int] = 2
    eval_batch_size: Optional[int] = None
    num_epochs: Optional[int] = None
    warmup_steps: Optional[int] = None
    warmup_ratio: Optional[float] = None
    learning_rate: Optional[float] = None
    lr_quadratic_warmup: Optional[bool] = None
    logging_steps: Optional[int] = None
    eval_steps: Optional[Union[int, float]] = None
    evals_per_epoch: Optional[int] = None
    eval_strategy: Optional[str] = None
    save_strategy: Optional[str] = None
    save_steps: Optional[Union[int, float]] = None
    saves_per_epoch: Optional[int] = None
    save_total_limit: Optional[int] = None
    max_steps: Optional[int] = None
    include_tokens_per_second: Optional[bool] = None
    auto_find_batch_size: Optional[bool] = None
    
    # Evaluation options
    eval_table_size: Optional[int] = None
    eval_max_new_tokens: Optional[int] = None
    do_causal_lm_eval: Optional[bool] = None
    eval_causal_lm_metrics: Optional[List[str]] = None
    
    # Profiling and debugging
    profiler_steps: Optional[int] = None
    loss_watchdog_threshold: Optional[float] = None
    loss_watchdog_patience: Optional[int] = None
    
    # Save options
    save_safetensors: Optional[bool] = None
    
    # Training options
    train_on_inputs: Optional[bool] = False
    group_by_length: Optional[bool] = False
    gradient_checkpointing: Optional[Union[bool, str]] = False
    early_stopping_patience: Optional[int] = None
    
    # Scheduler configuration
    lr_scheduler: Optional[str] = None
    lr_scheduler_kwargs: Optional[Dict[str, Any]] = None
    cosine_min_lr_ratio: Optional[float] = None
    cosine_constant_lr_ratio: Optional[float] = None
    lr_div_factor: Optional[float] = None
    
    # Optimizer options
    optimizer: Optional[str] = None
    optim_args: Optional[Dict[str, Any]] = None
    optim_target_modules: Optional[List[str]] = None
    weight_decay: Optional[float] = None
    adam_beta1: Optional[float] = None
    adam_beta2: Optional[float] = None
    adam_epsilon: Optional[float] = None
    max_grad_norm: Optional[float] = None
    
    # Augmentation techniques
    neftune_noise_alpha: Optional[float] = None
    
    # Optimization techniques
    flash_optimum: Optional[bool] = None
    xformers_attention: Optional[bool] = None
    flash_attention: Optional[bool] = None
    flash_attn_cross_entropy: Optional[bool] = None
    flash_attn_rms_norm: Optional[bool] = None
    flash_attn_fuse_qkv: Optional[bool] = None
    flash_attn_fuse_mlp: Optional[bool] = None
    sdp_attention: Optional[bool] = None
    s2_attention: Optional[bool] = None
    
    # Memory options
    low_cpu_mem_usage: Optional[bool] = None
    
    # Checkpointing
    resume_from_checkpoint: Optional[str] = None
    auto_resume_from_checkpoints: Optional[bool] = False
    
    # Multimodal options
    image_size: Optional[Union[int, Tuple[int, int]]] = None
    image_resize_algorithm: Optional[str] = 'bilinear'
    
    # For distributed training
    local_rank: Optional[int] = None
    
    # Token handling
    special_tokens: Optional[SpecialTokens] = None
    tokens: Optional[List[str]] = None
    added_tokens_overrides: Optional[Dict[int, str]] = None
    
    # Distributed training
    fsdp: Optional[str] = None
    fsdp_config: Optional[Dict[str, Any]] = None
    deepspeed: Optional[str] = None
    ddp_timeout: Optional[int] = None
    ddp_bucket_cap_mb: Optional[int] = None
    ddp_broadcast_buffers: Optional[bool] = None
    
    # Sequence parallelism
    sequence_parallel_degree: Optional[int] = None
    heads_k_stride: Optional[int] = 1
    
    # Miscellaneous
    torchdistx_path: Optional[str] = None
    pretraining_dataset: Optional[str] = None
    debug: Optional[bool] = None
    seed: Optional[int] = None
    strict: Optional[bool] = None
    
    @validator("base_model_config", always=True)
    def set_default_base_model_config(cls, v, values):
        if v is None and "base_model" in values:
            return values["base_model"]
        return v
    
    @model_validator(mode='after')
    def validate_compatibility(self) -> 'AxolotlConfig':
        # Validate warmup settings
        if self.warmup_steps is not None and self.warmup_ratio is not None:
            raise ValueError("Cannot specify both warmup_steps and warmup_ratio")
        
        # Validate eval steps settings
        if self.eval_steps is not None and self.evals_per_epoch is not None:
            raise ValueError("Cannot specify both eval_steps and evals_per_epoch")
        
        # Validate save steps settings
        if self.save_steps is not None and self.saves_per_epoch is not None:
            raise ValueError("Cannot specify both save_steps and saves_per_epoch")
        
        # Validate val_set_size and test_datasets
        if self.val_set_size is not None and self.val_set_size > 0 and self.test_datasets:
            raise ValueError("Cannot specify both val_set_size and test_datasets")
        
        # Validate attention methods
        attention_methods = [
            "xformers_attention",
            "flash_attention",
            "sdp_attention",
            "s2_attention"
        ]
        
        enabled_methods = [
            method for method in attention_methods 
            if getattr(self, method, None) is not None and getattr(self, method)
        ]
        
        if len(enabled_methods) > 1:
            raise ValueError(f"Only one attention method can be enabled at a time. Found: {', '.join(enabled_methods)}")
        
        return self
    
    @validator("adapter")
    def validate_adapter(cls, v):
        if v is not None and v not in ["lora", "qlora", ""]:
            raise ValueError("adapter must be 'lora', 'qlora', or empty string")
        return v
