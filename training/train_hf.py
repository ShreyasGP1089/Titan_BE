"""
Fine-tune Qwen2.5-1.5B-Instruct for e-commerce search planning with Hugging Face + PEFT.

This is the clean production training path for Render/Linux deployment. It
uses the existing JSONL dataset in training/data without rewriting examples and
saves a standard PEFT adapter that hf_planner.py can load directly.
"""
import json
import torch
from pathlib import Path
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
import logging
import numpy as np  # OPTIMIZED: For token statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
OUTPUT_DIR = SCRIPT_DIR / "outputs/qwen25_1_5b_lora_hf"
DATASET_PATH = SCRIPT_DIR / "data/train.jsonl"

# Training hyperparameters
LEARNING_RATE = 5e-5  # FIXED: Reduced from 2e-4 (more stable)
NUM_EPOCHS = 1  # OPTIMIZED: Reduced to 1 for speed testing (was 2)
BATCH_SIZE = 1  # OPTIMIZED: Already optimal for MPS
GRADIENT_ACCUMULATION_STEPS = 4  # FIXED: Reduced from 8 (faster feedback)
LORA_RANK = 8
LORA_ALPHA = 16
MAX_SEQ_LENGTH = 512  # OPTIMIZED: Reduced from 2048 (2x-4x speedup)
MAX_GRAD_NORM = 1.0  # FIXED: Added gradient clipping
USE_QLORA = torch.cuda.is_available()

# LoRA target modules for Qwen
LORA_TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj"
]


class NaNDetectionCallback(TrainerCallback):
    """Callback to detect NaN in model parameters during training."""
    
    def on_step_end(self, args, state, control, **kwargs):
        """Check for NaN after each training step (only LoRA params, every 50 steps)."""
        model = kwargs.get("model")
        if model is not None and state.global_step % 50 == 0:  # FIXED: Check every 50 steps (not 10)
            for name, param in model.named_parameters():
                if param.requires_grad:  # Only check LoRA params (~33M, not full 4B)
                    if torch.isnan(param.data).any():  # FIXED: Check .data directly
                        logger.error(f"❌ NaN detected in parameter: {name}")
                        logger.error(f"   Step: {state.global_step}")
                        logger.error(f"   Loss: {state.log_history[-1] if state.log_history else 'N/A'}")
                        raise ValueError(f"Training diverged: NaN found in {name}")
        return control


def prepare_dataset(tokenizer):
    """
    Load and prepare the dataset for training.
    
    Args:
        tokenizer: Hugging Face tokenizer
    
    Returns:
        Processed dataset
    """
    dataset_path = Path(DATASET_PATH)
    
    if not dataset_path.exists():
        logger.error(f"❌ Dataset not found at {dataset_path}")
        logger.error("   Please run: python convert_dataset.py")
        return None
    
    logger.info(f"📂 Loading dataset from {dataset_path}...")
    
    # FIXED: Validate dataset format before loading
    logger.info("🔍 Validating dataset format...")
    with open(dataset_path, 'r') as f:
        for i, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                if "text" not in data and "messages" not in data:
                    logger.error(f"❌ Line {i}: Missing 'text' or 'messages' key")
                    logger.error(f"   Content: {line[:100]}...")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"❌ Line {i}: Invalid JSON")
                logger.error(f"   Error: {e}")
                logger.error(f"   Content: {line[:100]}...")
                return None
    
    logger.info("✓ Dataset format validated")
    
    # Load JSONL dataset
    dataset = load_dataset('json', data_files=str(dataset_path), split='train')
    
    logger.info(f"✓ Loaded {len(dataset)} training examples")
    
    def format_example(example):
        """Format either chat-message or preformatted-text examples."""
        if "text" in example and example["text"]:
            return {"text": example["text"]}

        messages = example["messages"]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": text}
    
    # Format all examples
    logger.info("📝 Formatting examples with chat template...")
    dataset = dataset.map(format_example, remove_columns=dataset.column_names)
    
    def tokenize_function(examples):
        """Tokenize examples."""
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
            padding=False,  # OPTIMIZED: Dynamic padding (don't pad here)
            return_tensors=None
        )
    
    # Tokenize dataset
    logger.info("🔤 Tokenizing dataset...")
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
        desc="Tokenizing"
    )
    
    logger.info(f"✓ Dataset prepared: {len(tokenized_dataset)} examples")
    
    # OPTIMIZED: Print token length statistics
    logger.info("\n📊 Analyzing token lengths...")
    lengths = [len(x["input_ids"]) for x in tokenized_dataset]
    
    import numpy as np
    avg_length = np.mean(lengths)
    max_length = np.max(lengths)
    p95_length = np.percentile(lengths, 95)
    p99_length = np.percentile(lengths, 99)
    
    logger.info(f"   → Average: {avg_length:.1f} tokens")
    logger.info(f"   → Max: {max_length} tokens")
    logger.info(f"   → 95th percentile: {p95_length:.1f} tokens")
    logger.info(f"   → 99th percentile: {p99_length:.1f} tokens")
    
    if p95_length < MAX_SEQ_LENGTH * 0.5:
        logger.info(f"   ℹ️  95% of examples are <{MAX_SEQ_LENGTH//2} tokens")
        logger.info(f"   ℹ️  Consider reducing MAX_SEQ_LENGTH to {int(p99_length) + 50} for even faster training")
    
    return tokenized_dataset


def setup_model_and_tokenizer():
    """
    Load base model and tokenizer, apply LoRA.
    
    Returns:
        Tuple of (model, tokenizer)
    """
    logger.info(f"📥 Loading tokenizer from {BASE_MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_NAME,
        trust_remote_code=True
    )
    
    # Set padding token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    logger.info(f"📥 Loading base model from {BASE_MODEL_NAME}...")
    
    # Determine device and load model accordingly. QLoRA is useful on CUDA
    # training machines; CPU/MPS keeps a normal LoRA path for compatibility.
    if torch.cuda.is_available():
        logger.info(f"✓ CUDA available: {torch.cuda.get_device_name(0)}")
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16
        )
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_NAME,
            trust_remote_code=True,
            device_map="auto",
            quantization_config=quantization_config,
            torch_dtype=torch.bfloat16
        )
        model = prepare_model_for_kbit_training(model)
    else:
        logger.info("✓ No CUDA GPU available, using CPU/MPS-compatible LoRA load")
        # FIXED: Force float32 on MPS to avoid NaN issues
        # MPS fp16 is unstable for training large models
        # FIXED: Disable low_cpu_mem_usage to avoid meta tensor issues on M5 Air
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_NAME,
            trust_remote_code=True,
            torch_dtype=torch.float32,  # FIXED: Always use float32 on MPS/CPU
            low_cpu_mem_usage=False  # FIXED: M5 Air has enough RAM, avoid meta tensors
        )
    
    logger.info("✓ Base model loaded")
    
    # Configure LoRA
    logger.info("\n🔧 Configuring LoRA...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.0,
        target_modules=LORA_TARGET_MODULES,
        bias="none"
    )
    
    # Apply LoRA to model
    model = get_peft_model(model, lora_config)
    
    # FIXED: Disable cache for training (prevents issues with gradient checkpointing)
    model.config.use_cache = False
    
    # OPTIMIZED: Enable gradient checkpointing for memory efficiency on MPS
    model.gradient_checkpointing_enable()
    logger.info("✓ Gradient checkpointing enabled")
    
    # OPTIMIZED: Verify device placement
    device = next(model.parameters()).device
    logger.info(f"✓ Model device: {device}")
    if str(device) == "cpu":
        logger.warning("⚠️  Model is on CPU! MPS may not be working correctly.")
    
    # Print trainable parameters
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"✓ LoRA applied:")
    logger.info(f"   → Trainable params: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
    logger.info(f"   → Total params: {total_params:,}")
    
    return model, tokenizer


def train():
    """Main training function."""
    
    print("="*80)
    print("Fine-tuning Qwen2.5-1.5B-Instruct for E-commerce (Hugging Face)")
    print("="*80)
    
    # Setup model and tokenizer
    logger.info("\n🚀 Setting up model and tokenizer...")
    model, tokenizer = setup_model_and_tokenizer()
    
    # Prepare dataset
    logger.info("\n📊 Preparing dataset...")
    dataset = prepare_dataset(tokenizer)
    
    if dataset is None:
        return False
    
    # Create output directory
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # Training arguments
    logger.info("\n⚙️  Configuring training...")
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        gradient_checkpointing=True,  # OPTIMIZED: Enable for memory efficiency
        learning_rate=LEARNING_RATE,
        max_grad_norm=MAX_GRAD_NORM,  # FIXED: Added gradient clipping
        bf16=False,  # FIXED: Disabled (not stable on MPS)
        fp16=False,  # FIXED: Keep disabled (fp16 causes NaN on MPS)
        logging_steps=5,  # FIXED: More frequent logging to catch issues early
        save_steps=250,
        save_strategy="steps",  # FIXED: Explicit strategy
        save_total_limit=3,
        eval_strategy="no",  # FIXED: No eval (no val set)
        report_to="none",  # Disable wandb/tensorboard
        remove_unused_columns=False,
        dataloader_drop_last=False,  # FIXED: Keep all data (only ~1000 examples)
        optim="adamw_torch",  # FIXED: Standard AdamW (no 8bit on MPS)
        warmup_steps=10,  # FIXED: Reduced from 50 (only ~1000 examples, 0.4% warmup)
        lr_scheduler_type="cosine",
        logging_first_step=True,
        dataloader_pin_memory=False
    )
    
    logger.info(f"   → Epochs: {NUM_EPOCHS}")
    logger.info(f"   → Batch size: {BATCH_SIZE}")
    logger.info(f"   → Gradient accumulation: {GRADIENT_ACCUMULATION_STEPS}")
    logger.info(f"   → Effective batch size: {BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
    logger.info(f"   → Learning rate: {LEARNING_RATE}")
    logger.info(f"   → Max sequence length: {MAX_SEQ_LENGTH}")  # OPTIMIZED: Show seq length
    logger.info(f"   → QLoRA: {USE_QLORA}")
    logger.info(f"   → BF16: {training_args.bf16}")
    logger.info(f"   → Gradient checkpointing: {training_args.gradient_checkpointing}")  # OPTIMIZED: Show status
    
    # OPTIMIZED: Print comprehensive training configuration
    print("\n" + "="*80)
    print("📊 TRAINING CONFIGURATION SUMMARY")
    print("="*80)
    print(f"Model: {BASE_MODEL_NAME}")
    print(f"Device: {next(model.parameters()).device}")
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total parameters: {total_params:,} ({total_params/1e9:.2f}B)")
    print(f"Trainable parameters: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
    print(f"Max sequence length: {MAX_SEQ_LENGTH}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Gradient accumulation: {GRADIENT_ACCUMULATION_STEPS}")
    print(f"Effective batch size: {BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS}")
    print(f"Epochs: {NUM_EPOCHS}")
    print(f"Training examples: {len(dataset)}")
    steps_per_epoch = len(dataset) // (BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS)
    total_steps = steps_per_epoch * NUM_EPOCHS
    print(f"Steps per epoch: {steps_per_epoch}")
    print(f"Total training steps: {total_steps}")
    print("="*80 + "\n")
    
    # Data collator with dynamic padding
    # OPTIMIZED: Pads to longest sequence in batch, not MAX_SEQ_LENGTH
    # This can give 1.5x-2x speedup when sequences are shorter than max
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # Causal LM, not masked LM
        pad_to_multiple_of=8  # OPTIMIZED: Pad to multiple of 8 for hardware efficiency
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
        callbacks=[NaNDetectionCallback()]  # FIXED: Added NaN detection
    )
    
    # Start training
    logger.info("\n🎯 Starting training...")
    print("="*80)
    logger.info("⏱️  Training will take 1-3 hours depending on hardware")
    logger.info("💡 You'll see loss values decreasing as training progresses")
    print("="*80 + "\n")
    
    try:
        trainer.train()
        
        logger.info("\n💾 Saving final model...")
        trainer.save_model(str(OUTPUT_DIR))
        tokenizer.save_pretrained(str(OUTPUT_DIR))
        
        # Save training info
        info = {
            "base_model": BASE_MODEL_NAME,
            "framework": "Hugging Face Transformers + PEFT",
            "quantization": "QLoRA 4-bit NF4" if USE_QLORA else "LoRA",
            "task": "E-commerce Search Planning",
            "lora_rank": LORA_RANK,
            "lora_alpha": LORA_ALPHA,
            "target_modules": LORA_TARGET_MODULES,
            "epochs": NUM_EPOCHS,
            "learning_rate": LEARNING_RATE,
            "batch_size": BATCH_SIZE,
            "training_examples": len(dataset),
            "output_format": "Structured JSON for search requests"
        }
        
        with open(OUTPUT_DIR / "training_info.json", 'w') as f:
            json.dump(info, f, indent=2)
        
        print("\n" + "="*80)
        print("✅ Training completed successfully!")
        print("="*80)
        print(f"\n🎉 Model saved to: {OUTPUT_DIR}")
        print("\n💡 Next steps:")
        print("   1. Test the model: python test_hf_model.py")
        print("   2. Update API to use hf_planner.py")
        print("   3. Deploy to production server")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = train()
    exit(0 if success else 1)
