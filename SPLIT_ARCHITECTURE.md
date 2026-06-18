# Split Architecture Deployment Guide

## Overview

The application now uses a **split architecture** to work with Render's free tier (512 MB RAM):

```
Frontend
    ↓
Render Backend (FastAPI)
    ↓ HTTP
ngrok (tunnel)
    ↓ HTTP
Mac Local Server (FastAPI)
    ↓
Qwen2.5-1.5B-Instruct + LoRA
```

---

## Architecture

### Render Backend (512 MB RAM) ✅
- PostgreSQL + pgvector
- Sentence transformers embeddings (~100 MB)
- Hybrid search
- Product ranking
- **NO LLM MODEL** (saves ~3 GB RAM)

### Mac Local Server (Your Machine) 🖥️
- Qwen2.5-1.5B-Instruct (~3 GB)
- LoRA adapter (~50 MB)
- FastAPI server on port 8001
- Exposed via ngrok

---

## Setup Steps

### 1. Start Local Model Server (Mac)

```bash
# Terminal 1: Start model server
python3 local_model_server.py
```

**Expected output:**
```
🚀 Starting Local Model Server
   Port: 8001
   Model: Qwen/Qwen2.5-1.5B-Instruct
   Adapter: training/outputs/qwen25_1_5b_lora_hf
✓ Model ready on MPS
✅ Server ready for requests
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### 2. Expose with ngrok

```bash
# Terminal 2: Expose model server
ngrok http 8001
```

**Copy the ngrok URL:**
```
Forwarding  https://xxxx-xx-xxx-xxx-xxx.ngrok-free.app -> http://localhost:8001
```

### 3. Test Local Server

```bash
# Terminal 3: Test
python3 test_local_model.py
```

**Expected:**
```
✓ PASS Health Check
✓ PASS Direct HTTP
✓ PASS Client
✅ ALL TESTS PASSED
```

### 4. Configure Render

Set environment variable in Render:

```bash
LOCAL_MODEL_URL=https://xxxx-xx-xxx-xxx-xxx.ngrok-free.app
MODEL_REQUEST_TIMEOUT=120
```

### 5. Deploy to Render

```bash
git add .
git commit -m "Split architecture: Render backend + local model server"
git push
```

---

## File Structure

### Created Files ✅
```
local_model_server.py          # FastAPI server for Mac (Qwen + LoRA)
backend/local_model_client.py  # HTTP client for Render backend
test_local_model.py            # Test script
```

### Modified Files ✅
```
backend/hf_planner.py          # Now uses HTTP client instead of direct model
backend/api_swagger.py         # Removed model loading, uses HTTP client
backend/.env                   # Added LOCAL_MODEL_URL
```

### Unchanged Files ✅
```
backend/db.py                  # Database connection
backend/embedding.py           # Sentence transformers (still loads locally)
backend/tools.py               # Search functions
backend/search_pipeline.py     # Hybrid search
training/train_hf.py           # Training script (run locally)
```

---

## API Endpoints

### Local Model Server (Port 8001)

#### Health Check
```bash
GET http://localhost:8001/health
```

**Response:**
```json
{
  "status": "healthy",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps",
  "adapter_loaded": true
}
```

#### Generate
```bash
POST http://localhost:8001/generate
Content-Type: application/json

{
  "prompt": "Query: running shoes under 5000",
  "max_new_tokens": 256,
  "temperature": 0.0,
  "do_sample": false
}
```

**Response:**
```json
{
  "response": "{\"intent\": \"search\", ...}",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps",
  "tokens_generated": 45
}
```

### Render Backend (Port 5000)

Same as before, but now calls local model server internally.

---

## Environment Variables

### Mac Local Server
```bash
# No env vars needed - uses defaults
PORT=8001  # Optional
```

### Render Backend
```bash
# Database (from Render PostgreSQL)
POSTGRES_HOST=<render-postgres-host>
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=<render-user>
POSTGRES_PASSWORD=<render-password>

# API Key
API_KEY=<secure-key>

# Local Model Server (CRITICAL)
LOCAL_MODEL_URL=https://xxxx.ngrok-free.app
MODEL_REQUEST_TIMEOUT=120

# Embeddings (still loads locally on Render)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

---

## Memory Usage

### Render Backend (FREE TIER: 512 MB) ✅
```
PostgreSQL client:        ~50 MB
Sentence transformers:   ~100 MB
Flask + dependencies:    ~150 MB
Request buffers:          ~50 MB
---------------------------------
TOTAL:                   ~350 MB ✅ FITS!
```

### Mac Local Server
```
Python + FastAPI:        ~200 MB
Qwen2.5-1.5B-Instruct:  ~3000 MB
LoRA adapter:             ~50 MB
---------------------------------
TOTAL:                  ~3250 MB
```

---

## Testing

### 1. Test Local Server Only
```bash
python3 test_local_model.py
```

### 2. Test Backend Only (without model)
```bash
cd backend
python3 test_imports.py
```

### 3. Test Full Pipeline
```bash
# Start local server
python3 local_model_server.py &

# Start backend
cd backend
LOCAL_MODEL_URL=http://localhost:8001 python3 api_swagger.py

# Test smart search
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -d '{"query": "running shoes under 5000"}'
```

---

## Troubleshooting

### ❌ "Cannot connect to local model server"

**Cause:** Local server not running or ngrok tunnel down

**Fix:**
```bash
# Check local server
curl http://localhost:8001/health

# Check ngrok
curl https://xxxx.ngrok-free.app/health

# Restart if needed
python3 local_model_server.py
ngrok http 8001
```

### ❌ "Request timeout after 120s"

**Cause:** Model inference too slow

**Fix:**
```bash
# Increase timeout in Render
MODEL_REQUEST_TIMEOUT=180

# Or reduce prompt length
```

### ❌ "ngrok tunnel expired"

**Cause:** Free ngrok tunnels expire after 2 hours

**Fix:**
```bash
# Restart ngrok
ngrok http 8001

# Update Render env var with new URL
LOCAL_MODEL_URL=https://new-url.ngrok-free.app
```

### ❌ Render backend out of memory

**Cause:** Still trying to load model locally

**Fix:**
```bash
# Verify no model imports in backend code
grep -r "AutoModelForCausalLM" backend/

# Should only be in local_model_server.py (not in backend/)
```

---

## Deployment Checklist

### Local Setup (Mac)
- [ ] Train adapter: `python3 training/train_hf.py`
- [ ] Verify adapter exists: `training/outputs/qwen25_1_5b_lora_hf/`
- [ ] Test local server: `python3 local_model_server.py`
- [ ] Test generation: `python3 test_local_model.py`
- [ ] Start ngrok: `ngrok http 8001`
- [ ] Copy ngrok URL

### Render Setup
- [ ] Create PostgreSQL database
- [ ] Create Web Service (512 MB FREE tier OK!)
- [ ] Set `LOCAL_MODEL_URL` to ngrok URL
- [ ] Set `MODEL_REQUEST_TIMEOUT=120`
- [ ] Set database credentials
- [ ] Set `API_KEY`
- [ ] Deploy

### Testing
- [ ] Health check: `GET /api/v1/system/health`
- [ ] Parse query: `POST /api/v1/shopping/parse-query`
- [ ] Smart search: `POST /api/v1/shopping/smart-search`
- [ ] Verify response time < 45s

---

## Advantages

### ✅ Pros
1. **Fits in Render FREE tier** (512 MB RAM)
2. **No model download on Render** (faster deploys)
3. **Use powerful Mac hardware** (MPS GPU)
4. **Easy to update model** (just restart local server)
5. **Keep full 1.5B model** (no quantization needed)

### ⚠️ Cons
1. **Mac must be running** for API to work
2. **ngrok tunnel** must stay active
3. **Higher latency** (network roundtrip)
4. **Free ngrok** expires after 2 hours

---

## Production Considerations

### For Long-term Production

**Option 1: Paid ngrok**
- Permanent URLs
- No expiration
- Custom domains
- $8/month

**Option 2: VPS for Model Server**
- DigitalOcean/Linode: $12/month
- 4 GB RAM droplet
- Run `local_model_server.py` there
- Point Render to VPS IP

**Option 3: Upgrade Render**
- Render Standard: $25/month (2 GB RAM)
- Still not enough for 1.5B model
- Would need Pro: $85/month (8 GB RAM)

**Recommended:** Option 1 (paid ngrok) or Option 2 (VPS)

---

## Summary

### What Changed
- ❌ **Removed**: Model loading from Render backend
- ❌ **Removed**: HuggingFace transformers from Render
- ❌ **Removed**: PEFT from Render
- ✅ **Added**: HTTP client on Render
- ✅ **Added**: Local model server on Mac
- ✅ **Added**: ngrok tunnel

### What Stayed
- ✅ PostgreSQL + pgvector
- ✅ Sentence transformers embeddings
- ✅ Hybrid search
- ✅ All API endpoints

### Result
- **Render RAM usage**: 512 MB → ~350 MB ✅
- **Can use FREE tier**: YES ✅
- **Performance**: Same (20-40s per query)
- **Model**: Full 1.5B (no compromises)

---

**Status: READY FOR RENDER FREE TIER** 🎉

Start with:
```bash
python3 local_model_server.py
ngrok http 8001
# Copy ngrok URL to Render
```
