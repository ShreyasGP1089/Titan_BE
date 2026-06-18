# 🚀 Start the API

## Quick Start

### 1. Verify Configuration
```bash
cd backend
python3 test_imports.py
```

**Expected:** All imports successful ✅

### 2. Start the API
```bash
python3 api_swagger.py
```

### 3. Open Swagger UI
```
http://localhost:5000/docs
```

---

## What to Expect

### Startup Sequence
```
🚀 Starting API with HuggingFace Qwen2.5-1.5B-Instruct
✓ HuggingFace planner imported successfully
🔧 INITIALIZING BACKEND
1️⃣  Initializing PostgreSQL connection pool...
✓ PostgreSQL pool ready
2️⃣  Loading sentence-transformers embedding model...
   Model: sentence-transformers/all-MiniLM-L6-v2
✓ Embedding model loaded
✓ Backend initialization complete
 * Running on http://0.0.0.0:5000
```

### First Request
On the first API request to `/smart-search` or `/parse-query`:
```
Loading fine-tuned model...
Loading tokenizer from Qwen/Qwen2.5-1.5B-Instruct...
Loading base model from Qwen/Qwen2.5-1.5B-Instruct...
⏳ This will take 30-60 seconds on first load...
✓ Using Apple Metal (MPS) GPU acceleration
Moving model to mps...
Attempting to load LoRA adapter from ../training/outputs/qwen25_1_5b_lora_hf...
✓ LoRA adapter loaded successfully!
   Using fine-tuned Qwen2.5-1.5B adapter for better JSON parsing
✓ Model loaded on MPS
✓ Model ready for inference
```

**Note:** Model loads on first request (not at startup) to avoid health check timeout.

---

## Test Commands

### 1. Health Check
```bash
curl http://localhost:5000/api/v1/system/health
```

### 2. Parse Query
```bash
curl -X POST http://localhost:5000/api/v1/shopping/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

### 3. Smart Search (with API key)
```bash
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -d '{"query": "I want to start running"}'
```

---

## Common Issues

### ❌ ImportError: No module named 'transformers'
```bash
pip install -r requirements.txt
```

### ❌ Database connection error
- Check PostgreSQL is running: `pg_isready`
- Verify credentials in `.env`

### ❌ Adapter not found
```bash
# Train the adapter first
cd ../training
python3 train_hf.py
```

### ❌ Port 5000 in use
```bash
# Change PORT in .env or kill process
export PORT=5001
python3 api_swagger.py
```

---

## Configuration

All settings in `backend/.env`:
```bash
HF_BASE_MODEL_NAME=Qwen/Qwen2.5-1.5B-Instruct
HF_ADAPTER_PATH=../training/outputs/qwen25_1_5b_lora_hf
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
PRELOAD_MODEL=false
POSTGRES_HOST=localhost
POSTGRES_DB=decathlon_rag
```

---

## Ready to Deploy?

See: **`READY_FOR_DEPLOYMENT.md`** for Render deployment steps.

---

**Backend is configured and ready!** 🎉
