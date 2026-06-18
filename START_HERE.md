# 🚀 START HERE - Apple Silicon M5 Air

Quick guide to get your local model server running.

---

## ⚡ Quick Start (2 Commands)

```bash
# 1. Fix environment (removes NumPy 2.x and bitsandbytes)
./fix_local_env.sh

# 2. Start server
python3 local_model_server.py
```

That's it! Server will be running on `http://localhost:8001`

---

## ✅ What to Expect

### After `./fix_local_env.sh`:
```
✅ SUCCESS - Environment is ready!

Package versions:
✓ numpy              1.26.x
✓ torch              2.x.x
✓ transformers       4.x.x
✓ peft               0.x.x
✓ bitsandbytes not found (good)
✓ MPS available: True
```

### After `python3 local_model_server.py`:
```
Selected device: MPS (Apple Silicon)

🤖 LOADING MODEL
✓ Tokenizer loaded
✓ Base model loaded
✓ Model moved to MPS
✓ LoRA adapter loaded successfully!
✓ Model ready on MPS

✅ Server ready for requests
```

---

## 🧪 Test It

### In another terminal:
```bash
python3 test_local_model.py
```

**Expected:**
```
✅ ALL TESTS PASSED

✓ PASS   Health Check
✓ PASS   Direct HTTP
✓ PASS   Client
✓ PASS   Parse Query Endpoint
✓ PASS   Client Parse Query
```

---

## ❌ If You See Errors

### Error: NumPy 2.x
```bash
./fix_local_env.sh
```

### Error: bitsandbytes
```bash
pip uninstall -y bitsandbytes
./fix_local_env.sh
```

### Error: Check what's wrong
```bash
python3 check_environment.py
```

---

## 📚 Full Documentation

- **Quick Start:** `QUICKSTART_APPLE_SILICON.md`
- **Fix Guide:** `APPLE_SILICON_FIX.md`
- **Environment:** `ENVIRONMENT_FIX_COMPLETE.md`
- **Testing:** `TEST_AND_DEPLOY.md`

---

## 🎯 Next Steps After Local Testing

1. **Expose with ngrok:**
   ```bash
   ngrok http 8001
   ```

2. **Test ngrok:**
   ```bash
   curl https://YOUR-NGROK-URL/health
   ```

3. **Deploy to Render:**
   - Set `LOCAL_MODEL_URL=https://YOUR-NGROK-URL`
   - Push: `git push origin main`

---

## 💡 Key Points

- ✅ Use NumPy < 2.0 (not 2.x)
- ✅ NO bitsandbytes (incompatible with MPS)
- ✅ Uses MPS backend (Apple Silicon GPU)
- ✅ Model: Qwen2.5-1.5B-Instruct + LoRA
- ✅ Server: FastAPI on port 8001

---

**Ready? Run this:**
```bash
./fix_local_env.sh && python3 local_model_server.py
```
