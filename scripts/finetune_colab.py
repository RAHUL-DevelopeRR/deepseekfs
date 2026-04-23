"""
Neuron — LoRA Fine-Tuning Script for Google Colab
====================================================
Run this in Google Colab to fine-tune SmolLM3-3B on RLHF feedback data.

INSTRUCTIONS:
  1. Upload your training_data.jsonl (from scripts/export_training_data.py)
  2. Run this script in a Colab notebook with GPU runtime
  3. Download the output adapter files
  4. Place adapter in storage/models/lora_adapter/

Colab setup:
  !pip install peft transformers datasets bitsandbytes accelerate
  # Then run this script
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────
MODEL_NAME = "HuggingFaceTB/SmolLM2-1.7B-Instruct"  # Base model on HF
TRAINING_FILE = "training_data.jsonl"  # Upload this from Neuron export
OUTPUT_DIR = "neuron_lora_adapter"
LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
EPOCHS = 3
BATCH_SIZE = 4
LEARNING_RATE = 2e-4
MAX_SEQ_LENGTH = 512


def load_training_data(path: str) -> list:
    """Load JSONL training data."""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                # Only use positive examples for SFT
                if entry.get("rating", 1) > 0:
                    data.append(entry)
    print(f"Loaded {len(data)} positive training examples")
    return data


def format_for_training(examples: list) -> list:
    """Convert to chat format strings."""
    formatted = []
    for ex in examples:
        messages = ex.get("messages", [])
        if len(messages) >= 2:
            user_msg = messages[0]["content"]
            assistant_msg = messages[1]["content"]
            # SmolLM chat format
            text = (
                f"<|im_start|>user\n{user_msg}<|im_end|>\n"
                f"<|im_start|>assistant\n{assistant_msg}<|im_end|>"
            )
            formatted.append({"text": text})
    return formatted


def train():
    """Run LoRA fine-tuning."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
    )

    print(f"\n{'='*50}")
    print(f"  Neuron LoRA Fine-Tuning")
    print(f"  Model: {MODEL_NAME}")
    print(f"  LoRA rank={LORA_RANK}, alpha={LORA_ALPHA}")
    print(f"{'='*50}\n")

    # ── Load model ────────────────────────────────────────
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto",
        load_in_4bit=True,
    )

    # ── Configure LoRA ────────────────────────────────────
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Load training data ────────────────────────────────
    raw_data = load_training_data(TRAINING_FILE)
    formatted = format_for_training(raw_data)

    if len(formatted) < 5:
        print(f"\nWARNING: Only {len(formatted)} examples. "
              f"Need at least 50 for meaningful fine-tuning.")
        print("Collect more feedback data and re-export.")
        return

    dataset = Dataset.from_list(formatted)

    def tokenize_fn(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
            padding="max_length",
        )

    tokenized = dataset.map(tokenize_fn, batched=True, remove_columns=["text"])

    # ── Training ──────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=2,
        learning_rate=LEARNING_RATE,
        warmup_steps=10,
        logging_steps=5,
        save_strategy="epoch",
        fp16=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    print("\nStarting training...")
    trainer.train()

    # ── Save adapter ──────────────────────────────────────
    adapter_path = Path(OUTPUT_DIR) / "final_adapter"
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))
    print(f"\nAdapter saved to: {adapter_path}")
    print(f"Adapter size: {sum(f.stat().st_size for f in adapter_path.rglob('*') if f.is_file()) / 1024 / 1024:.1f} MB")
    print(f"\nTo use: copy {adapter_path} to your Neuron storage/models/lora_adapter/")


if __name__ == "__main__":
    train()
