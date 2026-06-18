# Quick Start: Split Architecture

## 🎯 Goal

Deploy to **Render FREE tier** (512 MB RAM) by running the LLM on your Mac.

---

## ⚡ Quick Start (5 Steps)

### Step 1: Install Dependencies

```bash
# Local model server (Mac)
pip install -r requirements_local_server.txt

# Backend (for local testing)
pip install -r backend/requirements_render.txt
```

### Step 2: Start Local Model Server

```bash
python3 local_model_server.py
```

**Wait for:**
```
✓ Model ready on MPS
✅ Server ready for requests
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Step 3: Test Local Server

```bash
# In another terminal
python3 test_local_model.py
```

**Expected:**
```
✅ ALL TESTS PASSED
```

### Step 4: Expose with ngrok

```bash
ngrok http 8001
```

**Copy the URL:**
```
Forwarding  https://xxxx-yyyy-zzzz.ngrok-free.app -> http://localhost:8001
              └──────────────┬──────────────┘
                     Copy this URL
```

### Step 5: Configure Render

Set in Render environment variables:
```bash
LOCAL_MODEL_URL=https://xxxx-yyyy-zzzz.ngrok-free.app
MODEL_REQUEST_TIMEOUT=120
```

Deploy and done! ✅

---

## 📁 Project Structure

```
Toolset/
├── local_model_server.py          # NEW: Runs on Mac (Qwen + LoRA)
├── test_local_model.py            # NEW: Test local server
├── requirements_local_server.txt   # NEW: Local server deps
│
├── backend/
│   ├── local_model_client.py      # NEW: HTTP client
│   ├── api_swagger.py             # MODIFIED: No model loading
│   ├── hf_planner.py              # MODIFIED: Uses HTTP client
│   ├── requirements_render.txt    # NEW: Lightweight deps
│   ├── db.py                      # Unchanged
│   ├── tools.py                   # Unchanged
│   └── embedding.py               # Unchanged
│
└── training/
    ├── train_hf.py                # Unchanged
    └── outputs/
        └── qwen25_1_5b_lora_hf/   # LoRA adapter
```

---

## 🧪 Testing

### Test 1: Local Server Only

```bash
# Start server
python3 local_model_server.py

# Test (in another terminal)
python3 test_local_model.py
```

### Test 2: Backend with Local Server

```bash
# Make sure local server is running first

# Start backend
cd backend
LOCAL_MODEL_URL=http://localhost:8001 python3 api_swagger.py

# Test
curl -X POST http://localhost:5000/api/v1/shopping/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

### Test 3: Full Pipeline

```bash
# With both servers running
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -d '{"query": "I want to start running"}'
```

---

## 🚀 Deployment Flow

### Development (Local)
```
Browser → localhost:5000 (Backend)
            ↓ HTTP
          localhost:8001 (Model Server)
            ↓
          Qwen + LoRA
```

### Production (Render + Mac)
```
Browser → Render Backend (512 MB FREE)
            ↓ HTTPS
          ngrok tunnel
            ↓ HTTP
          Mac Local (Model Server)
            ↓
          Qwen + LoRA
```

---

## 📊 Memory Comparison

### Before (Failed on Free Tier)
```
Render Backend:
  - PostgreSQL client:     50 MB
  - Embeddings:           100 MB
  - Qwen2.5-1.5B:      3,000 MB  ❌
  - Flask:                150 MB
  -------------------------------
  TOTAL:               3,300 MB  ❌ TOO MUCH!
```

### After (Fits in Free Tier)
```
Render Backend:
  - PostgreSQL client:     50 MB
  - Embeddings:           100 MB
  - Flask:                150 MB
  - Buffers:               50 MB
  -------------------------------
  TOTAL:                 350 MB  ✅ FITS!

Mac Local Server:
  - Qwen2.5-1.5B:      3,000 MB
  - FastAPI:             200 MB
  -------------------------------
  TOTAL:               3,200 MB  (On your Mac)
```

---

## 🔧 Configuration

### backend/.env (Local Testing)
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=test

API_KEY=decathlon_smart_search_2024_secure_key_abc123xyz

LOCAL_MODEL_URL=http://localhost:8001
MODEL_REQUEST_TIMEOUT=120

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Render Environment Variables
```bash
# Database (from Render PostgreSQL service)
POSTGRES_HOST=<internal-host>
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=<username>
POSTGRES_PASSWORD=<password>

# API Security
API_KEY=<generate-secure-key>

# Model Server (YOUR MAC via ngrok)
LOCAL_MODEL_URL=https://xxxx.ngrok-free.app
MODEL_REQUEST_TIMEOUT=120

# Embeddings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

---

## ❓ FAQ

### Q: Do I need to keep my Mac running?
**A:** Yes, the model server must run on your Mac for the API to work.

### Q: What if ngrok expires?
**A:** Free ngrok tunnels expire after 2 hours. Restart and update Render env var.
- **Solution:** Use paid ngrok ($8/month) for permanent URLs.

### Q: Can I use a VPS instead of my Mac?
**A:** Yes! Deploy `local_model_server.py` to a VPS (4 GB RAM, ~$12/month).

### Q: What's the latency impact?
**A:** ~200-500ms network roundtrip. Total response time still 20-40s (model inference dominates).

### Q: Can I use Render paid plan instead?
**A:** Yes, but expensive:
- Free: 512 MB (doesn't fit model)
- Standard: 2 GB (~$25/month, still too small)
- Pro: 8 GB (~$85/month, fits model)
- **vs. Split architecture: FREE Render + ngrok $8/month = $8/month**

---

## 🐛 Common Issues

### ❌ "Cannot connect to local model server"

```bash
# Check local server is running
curl http://localhost:8001/health

# Check ngrok tunnel
curl https://xxxx.ngrok-free.app/health

# Restart if needed
python3 local_model_server.py
ngrok http 8001
```

### ❌ "Module 'transformers' not found" on Render

```bash
# Make sure you're using requirements_render.txt
# NOT requirements.txt

# In render.yaml or Render dashboard:
buildCommand: pip install -r backend/requirements_render.txt
```

### ❌ Model server crashes with OOM

```bash
# Your Mac needs ~4 GB free RAM
# Close other applications

# Or use smaller model (future):
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
```

---

## ✅ Success Checklist

### Local Setup
- [ ] `python3 local_model_server.py` starts successfully
- [ ] Server shows "Model ready on MPS"
- [ ] `python3 test_local_model.py` passes all tests
- [ ] `ngrok http 8001` shows forwarding URL
- [ ] Can access `https://xxxx.ngrok-free.app/health`

### Render Setup
- [ ] Created PostgreSQL database
- [ ] Created Web Service (FREE 512 MB tier)
- [ ] Set `LOCAL_MODEL_URL` to ngrok URL
- [ ] Set all environment variables
- [ ] Deployed successfully
- [ ] Health check passes
- [ ] Smart search works

---

## 📚 Next Steps

1. **Get ngrok permanent URL** ($8/month)
   - Sign up: https://ngrok.com
   - Get authtoken
   - Configure: `ngrok config add-authtoken <token>`
   - Use static domain

2. **OR: Deploy model server to VPS**
   - DigitalOcean/Linode 4 GB droplet
   - Install dependencies
   - Run `local_model_server.py`
   - Point Render to VPS IP

3. **Monitor and optimize**
   - Check response times
   - Monitor ngrok bandwidth
   - Optimize prompts for speed

---

**Ready to deploy?** Start with Step 1! 🚀
