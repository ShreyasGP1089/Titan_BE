# Quick Start - Apple Silicon (M1/M2/M3/M4/M5)

**Platform:** macOS with Apple Silicon  
**Model:** Qwen2.5-1.5B-Instruct + LoRA  
**Backend:** MPS (Metal Performance Shaders)  
**NO CUDA, NO bitsandbytes**

---

## 🚀 Quick Start (4 Steps)

### Step 1: Fix Environment
```bash
./fix_local_env.sh
```

**What it does:**
- Removes NumPy 2.x (incompatible)
- Removes bitsandbytes (incompatible with MPS)
- Installs NumPy 1.x
- Installs compatible PyTorch, transformers, PEFT
- Verifies installation

**Expected output:**
```
✅ SUCCESS - Environment is ready!
```

---

### Step 2: Start Local Server
```bash
python3 local_model_server.py
```

**Expected output:**
```
ENVIRONMENT DIAGNOSTICS
PyTorch version: 2.x.x
NumPy version: 1.26.x
MPS available: True
Selected device: MPS (Apple Silicon)

🤖 LOADING MODEL
✓ Tokenizer loaded
✓ Base model loaded
✓ Model moved to MPS
✓ LoRA adapter loaded successfully!
✓ Model ready on MPS

✅ Server ready for requests
```

**Server is now running on:** `http://localhost:8001`

---

### Step 3: Test Server (New Terminal)
```bash
python3 test_local_model.py
```

**Expected output:**
```
✅ ALL TESTS PASSED

TEST SUMMARY
✓ PASS   Health Check
✓ PASS   Direct HTTP
✓ PASS   Client
✓ PASS   Parse Query Endpoint
✓ PASS   Client Parse Query
```

---

### Step 4: Expose with ngrok (New Terminal)
```bash
ngrok http 8001
```

**Copy the HTTPS URL:**
```
Forwarding: https://xxxx-xx-xx-xx-xxx.ngrok-free.app -> http://localhost:8001
```

**Test ngrok:**
```bash
curl https://YOUR-NGROK-URL/health
```

**Deploy to Render:**
- Set `LOCAL_MODEL_URL=https://YOUR-NGROK-URL`
- Push to git: `git push origin main`

---

## 🔍 Troubleshooting

### NumPy 2.x Error
```
Error: A module compiled using NumPy 1.x cannot be run in NumPy 2.x
```

**Fix:**
```bash
pip uninstall -y numpy
pip install "numpy<2.0.0"
```

---

### bitsandbytes Error
```
Error: module 'torch.library' has no attribute 'impl_abstract'
```

**Fix:**
```bash
pip uninstall -y bitsandbytes
# Don't reinstall - not needed for MPS
```

---

### MPS Not Available
```
Error: MPS not available
```

**Check:**
```bash
python3 -c "import torch; print(torch.backends.mps.is_available())"
```

If `False`, reinstall PyTorch:
```bash
pip install torch torchvision
```

---

### Adapter Not Found
```
Error: LoRA adapter not found
```

**Fix:**
```bash
python3 training/train_hf.py
```

---

## 📊 System Requirements

- **Mac:** M1, M2, M3, M4, or M5 chip
- **RAM:** 8 GB minimum, 16 GB recommended
- **Python:** 3.9 or higher
- **Storage:** ~5 GB for model + adapter

---

## 🛠️ Diagnostic Commands

### Check environment
```bash
python3 check_environment.py
```

### Verify deployment readiness
```bash
./verify_ready.sh
```

### Check PyTorch device
```bash
python3 -c "import torch; print(f'MPS: {torch.backends.mps.is_available()}')"
```

### Check NumPy version
```bash
python3 -c "import numpy; print(f'NumPy: {numpy.__version__}')"
```

### Check for bitsandbytes
```bash
python3 -c "import bitsandbytes" 2>&1 | grep -q "No module" && echo "✓ Not installed (good)" || echo "✗ Installed (bad)"
```

---

## 📝 Key Points

### ✅ DO:
- Use NumPy < 2.0
- Use MPS backend (Apple Silicon GPU)
- Load model with `torch.float16`
- Move model to MPS with `.to("mps")`
- Use PEFT for LoRA adapter

### ❌ DON'T:
- Use NumPy 2.x (incompatible)
- Install bitsandbytes (incompatible with MPS)
- Use `device_map="auto"` (use manual `.to("mps")`)
- Use quantization (4-bit/8-bit not supported on MPS)
- Use CUDA (not available on Apple Silicon)

---

## 🎯 Success Indicators

When everything works:
- ✅ Server starts without errors
- ✅ "Selected device: MPS" shown in logs
- ✅ LoRA adapter loads successfully
- ✅ Health endpoint returns 200
- ✅ All 5 tests pass
- ✅ Model generates valid JSON responses

---

## 📚 Documentation

- **Detailed Fix Guide:** `APPLE_SILICON_FIX.md`
- **Full Deployment Guide:** `TEST_AND_DEPLOY.md`
- **Architecture:** `SPLIT_ARCHITECTURE.md`
- **Requirements:** `requirements_local_server.txt`

---

## 💡 Tips

### Faster Startup
The model loads in ~30-60 seconds on M5 Air. This is normal.

### Memory Usage
Monitor with:
```bash
# In another terminal while server running
python3 -c "import psutil; print(f'RAM: {psutil.virtual_memory().percent}%')"
```

### Development Workflow
Keep 3 terminals open:
1. **Terminal 1:** Server (`python3 local_model_server.py`)
2. **Terminal 2:** ngrok (`ngrok http 8001`)
3. **Terminal 3:** Testing/commands

---

**Ready to start?**
```bash
./fix_local_env.sh && python3 local_model_server.py
```

---

**Last Updated:** June 18, 2026  
**Platform:** Apple Silicon (M5 Air tested)  
**Status:** Production Ready
