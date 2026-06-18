# Test and Deploy - Quick Reference

## ✅ Pre-Deployment Checklist

### 1. Adapter Verification ✓
```bash
ls -lh training/outputs/qwen25_1_5b_lora_hf/
```

**Expected files:**
- ✓ `adapter_model.safetensors` (35 MB)
- ✓ `adapter_config.json`
- ✓ `tokenizer.json` (11 MB)

**Status:** ✅ VERIFIED - All files present

---

### 2. Install Dependencies

#### For Local Server (Mac)
```bash
pip install -r requirements_local_server.txt
```

**Dependencies:**
- PyTorch (CPU or MPS)
- Transformers
- PEFT
- FastAPI
- Uvicorn
- Sentence-transformers

#### For Render Backend
```bash
pip install -r backend/requirements_render.txt
```

**Dependencies:**
- Flask
- SQLAlchemy
- psycopg2-binary
- sentence-transformers
- pgvector
- requests
- **NO PyTorch** (lightweight)

---

### 3. Test Local Server

#### Start Server
```bash
python3 local_model_server.py
```

**Expected output:**
```
🤖 LOADING MODEL
📥 Loading tokenizer from Qwen/Qwen2.5-1.5B-Instruct...
✓ Tokenizer loaded
📥 Loading base model from Qwen/Qwen2.5-1.5B-Instruct...
✓ Base model loaded
📦 Loading LoRA adapter from training/outputs/qwen25_1_5b_lora_hf...
✓ LoRA adapter loaded successfully!
✓ Model ready on MPS
✅ Server ready for requests
```

**Server runs on:** `http://localhost:8001`

---

### 4. Run Tests

#### In a new terminal:
```bash
python3 test_local_model.py
```

**Tests:**
1. ✅ Health Check (`/health`)
2. ✅ Direct HTTP Generation (`/generate`)
3. ✅ LocalModelClient wrapper
4. ✅ Parse Query endpoint (`/parse-query`)
5. ✅ Client parse_query() method

**Expected result:**
```
✅ ALL TESTS PASSED
```

---

### 5. Manual Health Check

```bash
curl http://localhost:8001/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps",
  "adapter_loaded": true
}
```

---

### 6. Test Parse Query

```bash
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

**Expected response:**
```json
{
  "intent": "search",
  "search_request": {
    "sport": "Running",
    "category": "Running Shoes",
    "keywords": ["shoes"],
    "price_limit": 5000
  },
  "raw_response": "...",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps"
}
```

---

## 🌐 Expose with ngrok

### Install ngrok
```bash
# macOS
brew install ngrok

# Or download from: https://ngrok.com/download
```

### Expose Local Server
```bash
ngrok http 8001
```

**Expected output:**
```
Forwarding  https://xxxx-xx-xx-xx-xxx.ngrok-free.app -> http://localhost:8001
```

**Copy the HTTPS URL** (e.g., `https://1234-56-78-90-123.ngrok-free.app`)

---

### Test ngrok Tunnel

```bash
curl https://YOUR-NGROK-URL.ngrok-free.app/health
```

**Expected:**
```json
{
  "status": "healthy",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps",
  "adapter_loaded": true
}
```

---

## 🚀 Deploy to Render

### 1. Set Environment Variables

In Render dashboard, add:

```env
# Model Server
LOCAL_MODEL_URL=https://YOUR-NGROK-URL.ngrok-free.app
MODEL_REQUEST_TIMEOUT=120

# PostgreSQL
POSTGRES_HOST=your-postgres-host
POSTGRES_PORT=5432
POSTGRES_DB=your-db-name
POSTGRES_USER=your-username
POSTGRES_PASSWORD=your-password

# API
API_KEY=your-secure-api-key

# Embeddings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

**CRITICAL:** Replace `YOUR-NGROK-URL` with your actual ngrok URL

---

### 2. Deploy

```bash
git add .
git commit -m "Split architecture: Render backend + Mac local server"
git push origin main
```

Render will automatically deploy.

---

### 3. Verify Deployment

#### Test Render health
```bash
curl https://your-app.onrender.com/health
```

#### Test query parsing
```bash
curl -X POST https://your-app.onrender.com/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"query": "running shoes under 5000"}'
```

---

## 📊 Memory Usage

### Local Server (Mac)
- **Base Model:** ~1,500 MB
- **LoRA Adapter:** ~35 MB  
- **Runtime:** ~300 MB
- **Total:** ~3,250 MB

### Render Backend (FREE tier)
- **PostgreSQL:** ~150 MB
- **Embeddings:** ~200 MB
- **Flask + Dependencies:** ~100 MB
- **Total:** ~350 MB ✅ **Fits in 512 MB**

---

## ⚠️ Important Notes

### LoRA Adapter Loading
- ✅ **REQUIRED:** Server will FAIL if adapter missing
- ✅ **NO fallback:** Guarantees fine-tuned model is used
- ✅ **Validation:** Checks adapter path on startup

### JSON Response Format
- ✅ **/parse-query:** Returns structured JSON directly
- ✅ **No double parsing:** Client receives dict, not string
- ✅ **Clean API:** Matches backend contract

### ngrok Considerations
- Free tier has 40 requests/minute limit
- Tunnel expires after 8 hours (restart ngrok)
- Consider ngrok paid plan for production
- Alternative: Use a cloud server with static IP

---

## 🔄 Development Workflow

### 1. Local Development
```bash
# Terminal 1: Start local server
python3 local_model_server.py

# Terminal 2: Run tests
python3 test_local_model.py

# Terminal 3: Start backend locally
cd backend
python3 api_swagger.py
```

### 2. Production Setup
```bash
# Terminal 1: Start local server
python3 local_model_server.py

# Terminal 2: Expose with ngrok
ngrok http 8001

# Terminal 3: Deploy to Render
git push origin main
```

---

## 🎯 Success Criteria

- ✅ Local server loads LoRA adapter
- ✅ Health endpoint returns 200
- ✅ Parse query returns structured JSON
- ✅ All 5 tests pass
- ✅ ngrok tunnel accessible
- ✅ Render deployment < 512 MB RAM
- ✅ Backend connects to local server
- ✅ End-to-end query parsing works

---

## 🐛 Troubleshooting

### Server won't start
**Problem:** `FileNotFoundError: LoRA adapter not found`

**Solution:**
```bash
ls training/outputs/qwen25_1_5b_lora_hf/
# Train if missing:
python3 training/train_hf.py
```

---

### Tests timeout
**Problem:** `Request timeout (120s)`

**Solution:**
- Check server logs for errors
- Increase timeout in test script
- Verify model loaded successfully

---

### ngrok tunnel not accessible
**Problem:** `Cannot connect to ngrok URL`

**Solution:**
- Check ngrok is running: `ngrok http 8001`
- Test local first: `curl http://localhost:8001/health`
- Check firewall settings

---

### Render deployment fails
**Problem:** `Out of memory`

**Solution:**
- Verify using `requirements_render.txt` (NO PyTorch)
- Check `LOCAL_MODEL_URL` is set correctly
- Confirm ngrok tunnel is active

---

## 📝 Next Steps After Successful Deployment

1. **Monitor Performance:**
   - Track Render memory usage
   - Monitor ngrok request limits
   - Check response times

2. **Consider Production Setup:**
   - Replace ngrok with cloud server
   - Add Redis for caching
   - Implement request queuing

3. **Scale as Needed:**
   - Upgrade Render tier if needed
   - Add load balancing
   - Implement rate limiting

---

**Last Updated:** June 18, 2026
**Architecture:** Split (Render + Mac Local Server)
**Model:** Qwen2.5-1.5B-Instruct + LoRA
