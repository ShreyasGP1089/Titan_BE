"""
Convert an MLX LoRA adapter to Hugging Face PEFT format.

The current production target is Linux/Render, so the API must load the
adapter with transformers + PEFT instead of MLX. This converter is kept as a
bridge for existing MLX training runs; for the cleanest production path,
prefer training directly with train_hf.py.
"""
import json
import torch
import numpy as np
from pathlib import Path
from safetensors import safe_open
from safetensors.torch import save_file
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MLX_ADAPTER_PATH = SCRIPT_DIR / "outputs/qwen3_4b_lora"
DEFAULT_HF_ADAPTER_PATH = SCRIPT_DIR / "outputs/qwen25_3b_instruct_lora_hf"
HF_BASE_MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"


def convert_mlx_to_hf(
    mlx_adapter_path: Path = DEFAULT_MLX_ADAPTER_PATH,
    hf_adapter_path: Path = DEFAULT_HF_ADAPTER_PATH,
):
    """
    Convert MLX LoRA adapter to Hugging Face PEFT format.
    
    Note: This is a simplified converter. For production use, you should
    retrain using Hugging Face transformers + PEFT for best compatibility.
    """
    
    print("="*80)
    print("MLX to Hugging Face LoRA Adapter Converter")
    print("="*80)
    
    if not mlx_adapter_path.exists():
        logger.error(f"❌ MLX adapter not found at {mlx_adapter_path}")
        logger.error("   Please train the model first using train_mlx.py")
        return False
    
    # Create output directory
    hf_adapter_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"\n📂 Converting adapter from MLX to Hugging Face format...")
    logger.info(f"   Source: {mlx_adapter_path}")
    logger.info(f"   Destination: {hf_adapter_path}")
    
    try:
        # Load MLX adapter weights
        mlx_adapter_file = mlx_adapter_path / "adapters.safetensors"
        
        if not mlx_adapter_file.exists():
            logger.error(f"❌ MLX adapter file not found: {mlx_adapter_file}")
            return False
        
        logger.info(f"\n📥 Loading MLX adapter from {mlx_adapter_file}...")
        
        # Read MLX safetensors
        mlx_tensors = {}
        with safe_open(mlx_adapter_file, framework="numpy") as f:
            for key in f.keys():
                mlx_tensors[key] = f.get_tensor(key)
        
        logger.info(f"✓ Loaded {len(mlx_tensors)} tensors from MLX adapter")
        
        # Convert to Hugging Face format
        # MLX format: model.layers.{i}.{component}.lora_{a/b}
        # HF format: base_model.model.model.layers.{i}.{component}.lora_{A/B}.weight
        
        hf_tensors = {}
        transformed_layers = set()
        
        for mlx_key, mlx_tensor in mlx_tensors.items():
            # Convert MLX key to HF key
            # MLX: model.layers.20.self_attn.q_proj.lora_a
            # HF:  base_model.model.model.layers.20.self_attn.q_proj.lora_A.default.weight
            
            if "lora_a" in mlx_key:
                # Remove 'model.' prefix from MLX key and add HF PEFT prefix
                hf_key = mlx_key.replace("model.", "", 1)  # Remove only first occurrence
                hf_key = f"base_model.model.model.{hf_key}"
                hf_key = hf_key.replace("lora_a", "lora_A.default.weight")
                # Transpose lora_A: MLX stores as [in_features, rank], PEFT expects [rank, in_features]
                tensor = torch.from_numpy(mlx_tensor).T.contiguous()
            elif "lora_b" in mlx_key:
                # Remove 'model.' prefix from MLX key and add HF PEFT prefix
                hf_key = mlx_key.replace("model.", "", 1)  # Remove only first occurrence
                hf_key = f"base_model.model.model.{hf_key}"
                hf_key = hf_key.replace("lora_b", "lora_B.default.weight")
                # Transpose lora_B: MLX stores as [rank, out_features], PEFT expects [out_features, rank]
                tensor = torch.from_numpy(mlx_tensor).T.contiguous()
            else:
                continue  # Skip non-LoRA tensors

            parts = mlx_key.split(".")
            if len(parts) > 3 and parts[0] == "model" and parts[1] == "layers":
                transformed_layers.add(int(parts[2]))
            
            # Store transposed tensor
            hf_tensors[hf_key] = tensor
            logger.debug(f"Converted {mlx_key} -> {hf_key} | {mlx_tensor.shape} -> {tensor.shape}")
            logger.debug(f"Converted {mlx_key} ({mlx_tensor.shape}) -> {hf_key} ({tensor.shape})")
        
        logger.info(f"✓ Converted {len(hf_tensors)} tensors to HF format")
        
        # Save as HF safetensors
        hf_adapter_file = hf_adapter_path / "adapter_model.safetensors"
        save_file(hf_tensors, hf_adapter_file)
        logger.info(f"✓ Saved HF adapter to {hf_adapter_file}")
        
        # Load MLX config to get actual rank and scale.
        mlx_config_file = mlx_adapter_path / "adapter_config.json"
        if not mlx_config_file.exists():
            mlx_config_file = SCRIPT_DIR / "lora_config.json"
        
        lora_rank = 8  # Default
        lora_scale = 20.0  # mlx_lm default observed in adapter_config.json
        if mlx_config_file.exists():
            with open(mlx_config_file, 'r') as f:
                mlx_config = json.load(f)
                lora_rank = mlx_config.get("lora_parameters", {}).get("rank", 8)
                lora_scale = mlx_config.get("lora_parameters", {}).get("scale", 20.0)
                logger.info(f"✓ Detected LoRA rank from MLX config: {lora_rank}")
                logger.info(f"✓ Detected MLX LoRA scale from config: {lora_scale}")

        layers_to_transform = sorted(transformed_layers)
        if not layers_to_transform:
            logger.error("❌ Could not detect transformed layers from adapter keys")
            return False

        # PEFT uses scaling = lora_alpha / r. MLX stores a direct scale value.
        # Multiplying by rank preserves the effective adapter scale.
        lora_alpha = int(round(float(lora_scale) * int(lora_rank)))
        
        # Create adapter_config.json for HF PEFT
        adapter_config = {
            "base_model_name_or_path": HF_BASE_MODEL_NAME,
            "bias": "none",
            "fan_in_fan_out": False,
            "inference_mode": True,
            "init_lora_weights": True,
            "layers_pattern": "layers",
            "layers_to_transform": layers_to_transform,
            "lora_alpha": lora_alpha,
            "lora_dropout": 0.0,
            "modules_to_save": None,
            "peft_type": "LORA",
            "r": lora_rank,
            "revision": None,
            "target_modules": [
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj"
            ],
            "task_type": "CAUSAL_LM"
        }
        
        config_file = hf_adapter_path / "adapter_config.json"
        with open(config_file, 'w') as f:
            json.dump(adapter_config, f, indent=2)
        
        logger.info(f"✓ Saved adapter config to {config_file}")
        logger.info(f"✓ Layers to transform: {layers_to_transform}")
        logger.info(f"✓ PEFT LoRA alpha: {lora_alpha}")
        
        print("\n" + "="*80)
        print("✅ Conversion completed successfully!")
        print("="*80)
        print(f"\n📦 Hugging Face adapter saved to: {hf_adapter_path}")
        print("\n⚠️  IMPORTANT NOTE:")
        print("   This is a basic conversion. For production use, consider:")
        print("   1. Retraining with Hugging Face transformers + PEFT")
        print("   2. Testing the converted adapter thoroughly")
        print("   3. Fine-tuning again if accuracy drops")
        print("\n💡 Next steps:")
        print("   1. Test the adapter: python test_hf_adapter.py")
        print("   2. Update API to use hf_planner.py")
        print("   3. Deploy to Linux server")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = convert_mlx_to_hf()
    exit(0 if success else 1)
