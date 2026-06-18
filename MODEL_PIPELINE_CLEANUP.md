# Model Pipeline Cleanup

## Production Path

Use this path for Render/Linux:

```text
training/data/train.jsonl
  -> training/train_hf.py
  -> Qwen/Qwen3-4B
  -> PEFT LoRA or QLoRA
  -> training/outputs/qwen3_4b_hf/
  -> backend/hf_planner.py
  -> Render
```

Expected production adapter files:

```text
training/outputs/qwen3_4b_hf/adapter_model.safetensors
training/outputs/qwen3_4b_hf/adapter_config.json
```

## Keep

- `training/data/`: source training data.
- `training/train_hf.py`: production Hugging Face + PEFT trainer.
- `backend/hf_planner.py`: production inference planner.
- `training/outputs/qwen3_4b_lora/`: backup only. This is an MLX adapter trained from `mlx-community/Qwen2.5-3B-Instruct-4bit`, despite the Qwen3 folder name.

## Archive Or Ignore

- `training/outputs/shopping_agent_lora/`: old MLX experiment.
- `training/outputs/shopping_agent_lora_hf/`: old converted/experimental HF adapter.
- `training/outputs/qwen25_3b_instruct_lora_hf/`: temporary conversion output from the Qwen2.5 MLX adapter.
- `training/convert_mlx_to_hf.py`: historical bridge script only; not part of production.
- `training/train_mlx.py`, `training/inference_mlx.py`, `training/check_mlx.py`, `training/train_simple.py`: Mac/MLX experiments only.

## Do Not Use For Render

- MLX adapters.
- MLX conversion outputs.
- Any adapter whose `adapter_config.json` references `Qwen/Qwen2.5-*` or `mlx-community/*`.

Render should load `Qwen/Qwen3-4B` and `training/outputs/qwen3_4b_hf`.
