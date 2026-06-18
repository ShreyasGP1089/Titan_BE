#!/usr/bin/env python3
"""
Environment Diagnostic Script for Apple Silicon
Checks compatibility for local_model_server.py
"""

import sys

print("=" * 80)
print("ENVIRONMENT DIAGNOSTIC CHECK")
print("=" * 80)
print()

errors = []
warnings = []

# Check Python version
print(f"Python: {sys.version}")
python_version = sys.version_info
if python_version.major != 3 or python_version.minor < 9:
    errors.append(f"Python {python_version.major}.{python_version.minor} - need Python 3.9+")
else:
    print(f"✓ Python {python_version.major}.{python_version.minor} OK")
print()

# Check NumPy
print("Checking NumPy...")
try:
    import numpy as np
    print(f"  Version: {np.__version__}")
    if np.__version__.startswith('2.'):
        errors.append(f"NumPy {np.__version__} - incompatible! Need numpy<2.0.0")
        print(f"  ❌ NumPy 2.x is INCOMPATIBLE with transformers on Apple Silicon")
        print(f"     Run: pip uninstall -y numpy && pip install 'numpy<2.0.0'")
    else:
        print(f"  ✓ NumPy {np.__version__} OK")
except ImportError:
    errors.append("NumPy not installed")
    print("  ❌ NumPy not found")
print()

# Check PyTorch
print("Checking PyTorch...")
try:
    import torch
    print(f"  Version: {torch.__version__}")
    print(f"  CUDA available: {torch.cuda.is_available()}")
    print(f"  MPS available: {torch.backends.mps.is_available()}")
    print(f"  MPS built: {torch.backends.mps.is_built()}")
    
    if torch.backends.mps.is_available():
        print(f"  ✓ MPS (Apple Silicon) GPU available")
    elif torch.cuda.is_available():
        print(f"  ✓ CUDA GPU available")
    else:
        warnings.append("No GPU available - will use CPU (slower)")
        print(f"  ⚠️  No GPU - will use CPU")
except ImportError:
    errors.append("PyTorch not installed")
    print("  ❌ PyTorch not found")
print()

# Check transformers
print("Checking transformers...")
try:
    import transformers
    print(f"  Version: {transformers.__version__}")
    print(f"  ✓ Transformers installed")
except ImportError:
    errors.append("transformers not installed")
    print("  ❌ transformers not found")
print()

# Check PEFT
print("Checking PEFT...")
try:
    import peft
    print(f"  Version: {peft.__version__}")
    print(f"  ✓ PEFT installed")
except ImportError:
    errors.append("PEFT not installed")
    print("  ❌ PEFT not found")
print()

# Check accelerate
print("Checking accelerate...")
try:
    import accelerate
    print(f"  Version: {accelerate.__version__}")
    print(f"  ✓ accelerate installed")
except ImportError:
    errors.append("accelerate not installed")
    print("  ❌ accelerate not found")
print()

# Check FastAPI
print("Checking FastAPI...")
try:
    import fastapi
    print(f"  Version: {fastapi.__version__}")
    print(f"  ✓ FastAPI installed")
except ImportError:
    errors.append("FastAPI not installed")
    print("  ❌ FastAPI not found")
print()

# Check uvicorn
print("Checking uvicorn...")
try:
    import uvicorn
    print(f"  Version: {uvicorn.__version__}")
    print(f"  ✓ uvicorn installed")
except ImportError:
    errors.append("uvicorn not installed")
    print("  ❌ uvicorn not found")
print()

# Check safetensors
print("Checking safetensors...")
try:
    import safetensors
    print(f"  Version: {safetensors.__version__}")
    print(f"  ✓ safetensors installed")
except ImportError:
    errors.append("safetensors not installed")
    print("  ❌ safetensors not found")
print()

# Check for bitsandbytes (should NOT be installed)
print("Checking for bitsandbytes (should NOT be present)...")
try:
    import bitsandbytes
    errors.append("bitsandbytes is installed - incompatible with Apple Silicon MPS")
    print(f"  ❌ bitsandbytes found - this is INCOMPATIBLE with Apple Silicon")
    print(f"     Run: pip uninstall -y bitsandbytes")
except ImportError:
    print(f"  ✓ bitsandbytes not found (good)")
print()

# Check adapter path
print("Checking LoRA adapter...")
from pathlib import Path
adapter_path = Path("training/outputs/qwen25_1_5b_lora_hf")
if adapter_path.exists():
    adapter_files = list(adapter_path.glob("*"))
    print(f"  Path: {adapter_path}")
    print(f"  Files: {len(adapter_files)} files found")
    
    required_files = ["adapter_model.safetensors", "adapter_config.json"]
    for req_file in required_files:
        if (adapter_path / req_file).exists():
            print(f"    ✓ {req_file}")
        else:
            errors.append(f"Missing adapter file: {req_file}")
            print(f"    ❌ {req_file} not found")
else:
    errors.append(f"Adapter path not found: {adapter_path}")
    print(f"  ❌ Adapter not found at: {adapter_path}")
    print(f"     Train the adapter first: python3 training/train_hf.py")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)

if errors:
    print(f"\n❌ {len(errors)} ERROR(S) FOUND:\n")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. {error}")
    print()

if warnings:
    print(f"\n⚠️  {len(warnings)} WARNING(S):\n")
    for i, warning in enumerate(warnings, 1):
        print(f"  {i}. {warning}")
    print()

if not errors:
    print("\n✅ ENVIRONMENT IS READY!")
    print("\nYou can start the local model server:")
    print("  python3 local_model_server.py")
    print()
    sys.exit(0)
else:
    print("\n❌ ENVIRONMENT HAS ISSUES")
    print("\nFix the issues by running:")
    print("  ./fix_local_env.sh")
    print()
    sys.exit(1)
