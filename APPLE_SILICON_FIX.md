# Apple Silicon Environment Fix

**Problem:** NumPy 2.x and bitsandbytes incompatibility on Apple Silicon (M1/M2/M3/M4/M5)

**Solution:** Remove incompatible packages and install Apple Silicon compatible versions

---

## ⚠️ Current Issues

### Issue 1: NumPy 2.x Incompatibility
```
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x
Current NumPy: 2.4.6
```

**Cause:** transformers and other ML packages are compiled against NumPy 1.x

**Solution:** Downgrade to `numpy<2.0.0`

### Issue 2: bitsandbytes Incompatibility
```
AttributeError: module 'torch.library' has no attribute 'impl_abstract'
while importing: bitsandbytes
```

**Cause:** bitsandbytes doesn't support Apple Silicon MPS backend

**Solution:** Remove bitsandbytes completely (not needed for MPS)

---

## ✅ Quick Fix (Recommended)

### Option 1: Automated Fix Script
```bash
./fix_local_env.sh
```

This script will:
1. Remove bitsandbytes
2. Remove NumPy 2.x
3. Install NumPy 1.x
4. Install all compatible dependencies
5. Verify installation

### Option 2: Manual Fix
```bash
# 1. Remove incompatible packages
pip uninstall -y bitsandbytes
pip uninstall -y numpy

# 2. Install NumPy 1.x
pip install "numpy<2.0.0"

# 3. Install all dependencies
pip install -r requirements_local_server.txt

# 4. Verify
python3 check_environment.py
```

---

## 🔍 Verify Environment

### Before starting the server:
```bash
python3 check_environment.py
```

**Expected output:**
```
✓ Python 3.11 OK
✓ NumPy 1.x OK
✓ MPS (Apple Silicon) GPU available
✓ Transformers installed
✓ PEFT installed
✓ bitsandbytes not found (good)
✓ Adapter files present

✅ ENVIRONMENT IS READY!
```

---

## 📦 Compatible Dependencies

### requirements_local_server.txt
```
# NumPy MUST be < 2.0
numpy<2.0.0

# PyTorch for Apple Silicon
torch>=2.0.0,<2.5.0

# Transformers ecosystem
transformers>=4.36.0,<4.46.0
peft>=0.7.0,<0.14.0
accelerate>=0.25.0,<0.35.0

# Server
fastapi>=0.104.0,<0.115.0
uvicorn[standard]>=0.24.0,<0.32.0

# NO bitsandbytes!
```

---

## 🚀 Start Server

### After fixing environment:
```bash
python3 local_model_server.py
```

**Expected output:**
```
ENVIRONMENT DIAGNOSTICS
================================================================================
PyTorch version: 2.x.x
Transformers version: 4.x.x
PEFT version: 0.x.x
NumPy version: 1.26.x
CUDA available: False
MPS available: True
MPS built: True
Selected device: MPS (Apple Silicon)
================================================================================

🤖 LOADING MODEL
================================================================================
📥 Loading tokenizer from Qwen/Qwen2.5-1.5B-Instruct...
✓ Tokenizer loaded
📥 Loading base model from Qwen/Qwen2.5-1.5B-Instruct...
   Device: mps
   Dtype: torch.float16
✓ Base model loaded
📦 Moving model to MPS...
✓ Model moved to MPS
📦 Loading LoRA adapter from training/outputs/qwen25_1_5b_lora_hf...
✓ LoRA adapter loaded successfully!
✓ Model ready on MPS
================================================================================
✅ Server ready for requests
```

---

## 🔧 What Changed

### Code Changes

#### 1. requirements_local_server.txt
**Before:**
```python
torch>=2.0.0
transformers>=4.36.0
bitsandbytes>=0.41.0  # ❌ Incompatible
```

**After:**
```python
numpy<2.0.0  # ✅ Force NumPy 1.x
torch>=2.0.0,<2.5.0
transformers>=4.36.0,<4.46.0
# NO bitsandbytes ✅
```

#### 2. local_model_server.py

**Before:**
```python
from transformers import BitsAndBytesConfig  # ❌

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    device_map="auto",
    quantization_config=bnb_config  # ❌
)
```

**After:**
```python
# NO bitsandbytes imports ✅

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    low_cpu_mem_usage=True
)
model = model.to("mps")  # ✅ Manual device placement
model = PeftModel.from_pretrained(model, ADAPTER_PATH)
```

#### 3. Added Diagnostics

**On startup:**
```python
print(f"PyTorch version: {torch.__version__}")
print(f"Transformers version: {transformers.__version__}")
print(f"PEFT version: {peft.__version__}")
print(f"NumPy version: {np.__version__}")
print(f"MPS available: {torch.backends.mps.is_available()}")
print(f"Selected device: MPS")
```

---

## 📊 Memory Usage (Apple Silicon)

### With MPS (float16):
- Base Model: ~1,500 MB
- LoRA Adapter: ~35 MB
- Runtime: ~300 MB
- **Total: ~3,250 MB**

### Without bitsandbytes:
- **NO 8-bit quantization** (not needed on Apple Silicon)
- **NO 4-bit quantization** (not supported on MPS)
- **Full precision float16** works great on MPS

---

## 🐛 Troubleshooting

### Error: "NumPy 2.x cannot run"
```bash
pip uninstall -y numpy
pip install "numpy<2.0.0"
```

### Error: "bitsandbytes import failed"
```bash
pip uninstall -y bitsandbytes
# Don't reinstall - not needed for MPS
```

### Error: "MPS not available"
```python
# Check PyTorch installation
python3 -c "import torch; print(torch.backends.mps.is_available())"

# Should print: True
# If False, reinstall PyTorch:
pip install torch torchvision
```

### Error: "Adapter not found"
```bash
# Train the adapter
python3 training/train_hf.py
```

### Server starts but model crashes
```bash
# Check memory
# M5 Air should have enough RAM (8-16 GB)
# If issues persist, try float32 instead of float16
```

---

## ✅ Success Criteria

Environment is ready when:

- ✅ NumPy version < 2.0
- ✅ bitsandbytes NOT installed
- ✅ PyTorch reports MPS available
- ✅ Server starts without import errors
- ✅ Model loads on MPS device
- ✅ LoRA adapter loads successfully
- ✅ Health endpoint returns 200

---

## 📝 Commands Summary

```bash
# 1. Check current environment
python3 check_environment.py

# 2. Fix environment (if issues found)
./fix_local_env.sh

# 3. Verify fix
python3 check_environment.py

# 4. Start server
python3 local_model_server.py

# 5. Test in another terminal
python3 test_local_model.py
```

---

## 🎯 Architecture

```
Mac M5 Air (Apple Silicon)
  ↓
Python 3.11
  ↓
PyTorch 2.x (MPS backend)
  ├─ NO CUDA
  ├─ NO bitsandbytes
  └─ MPS (Metal Performance Shaders)
      ↓
Transformers + PEFT
  ├─ Qwen2.5-1.5B-Instruct (float16)
  └─ LoRA Adapter (35 MB)
      ↓
FastAPI Server (port 8001)
  ├─ /health
  ├─ /generate
  └─ /parse-query
      ↓
ngrok tunnel
      ↓
Render Backend
```

---

## 🔄 Migration from CUDA/bitsandbytes

If you had CUDA/bitsandbytes setup before:

### Removed:
- ❌ `bitsandbytes`
- ❌ `BitsAndBytesConfig`
- ❌ `load_in_8bit=True`
- ❌ `load_in_4bit=True`
- ❌ `device_map="auto"`
- ❌ `quantization_config`

### Added:
- ✅ `torch_dtype=torch.float16`
- ✅ `.to("mps")` manual device placement
- ✅ `low_cpu_mem_usage=True`
- ✅ MPS backend (Apple Silicon GPU)

### Same:
- ✅ Model: Qwen2.5-1.5B-Instruct
- ✅ LoRA adapter loading
- ✅ FastAPI endpoints
- ✅ Inference logic

---

**Last Updated:** June 18, 2026  
**Platform:** Apple Silicon (M1/M2/M3/M4/M5)  
**Python:** 3.11  
**Backend:** MPS (Metal Performance Shaders)  
**NO CUDA, NO bitsandbytes**
