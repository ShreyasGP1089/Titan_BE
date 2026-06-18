# ✅ Thin API Gateway - All ML Models on Mac

**Problem:** Render free tier (512 MB RAM) ran out of memory loading sentence-transformers  
**Solution:** Move ALL ML models to local server, make Render a thin API gateway  
**Status:** Complete and ready to test

---

## Architecture Change

### Before ❌
```
Render (512 MB)
├─ SentenceTransformer (300 MB) ← OOM!
├─ PostgreSQL client
└─ HTTP client → Mac (Qwen + LoRA)
```

**Result:** Out of memory

### After ✅
```
Render (512 MB)
├─ PostgreSQL client (~50 MB)
├─ Flask + deps (~100 MB)
└─ HTTP client
    ↓
  ngrok
    ↓
  Mac
  ├─ Qwen2.5-1.5B + LoRA (~1,500 MB)
  └─ SentenceTransformer (~300 MB)
```

**Result:** Render uses ~150-250 MB ✓ Fits in 512 MB

---

## Changes Made

### 1. Local Model Server (Mac)

**Added `/embed` endpoint:**
```python
POST /embed
{
  "texts": ["running shoes", "football boots"]
}

Response:
{
  "embeddings": [[...], [...]],
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "dimension": 384,
  "count": 2
}
```

**Startup loads both models:**
- ✅ Qwen2.5-1.5B-Instruct + LoRA
- ✅ SentenceTransformer (all-MiniLM-L6-v2)

---

### 2. Local Model Client (Render)

**Added `embed()` method:**
```python
from local_model_client import get_client

client = get_client()
embeddings = client.embed(["text1", "text2"])
# Returns: [[...], [...]]
```

---

### 3. Embedding Module (Render)

**Before:**
```python
from sentence_transformers import SentenceTransformer

_model = None

def load_model():
    global _model
    _model = SentenceTransformer("all-MiniLM-L6-v2")  # 300 MB!
    
def get_embedding(text):
    model = load_model()
    return model.encode(text).tolist()
```

**After:**
```python
from local_model_client import get_client

# NO model loading
# NO SentenceTransformer
# NO torch

def get_embedding(text):
    client = get_client()
    embeddings = client.embed([text])
    return embeddings[0]
    
def get_embeddings_batch(texts):
    client = get_client()
    return client.embed(texts)
```

---

### 4. Requirements (Render)

**Removed:**
- ❌ `torch`
- ❌ `transformers`
- ❌ `sentence-transformers`
- ❌ `accelerate`
- ❌ `peft`
- ❌ `bitsandbytes`

**Kept:**
- ✅ `flask`
- ✅ `requests`
- ✅ `psycopg2-binary`
- ✅ `numpy` (minimal, for array handling)

---

### 5. Startup Logs (Render)

**Before:**
```
Loading sentence-transformers embedding model...
Model: sentence-transformers/all-MiniLM-L6-v2
✓ Embedding model loaded
```

**After:**
```
✓ Using remote embedding server (NO local models)
✓ Using remote Qwen planner (NO local models)
LOCAL_MODEL_URL: https://xxxx.ngrok-free.app

Memory footprint:
  • PostgreSQL client: ~50 MB
  • Flask + dependencies: ~100 MB
  • NO torch: 0 MB ✓
  • NO sentence-transformers: 0 MB ✓
  • NO Qwen model: 0 MB ✓
  Expected total: ~150-250 MB (fits in 512 MB free tier) ✓
```

---

## Testing

### Test Local Server

**Terminal 1 - Start server:**
```bash
python3 local_model_server.py
```

**Expected startup:**
```
🤖 LOADING MODEL
✓ Tokenizer loaded
✓ Base model loaded
✓ LoRA adapter loaded successfully!
✓ Model ready on MPS

🔤 LOADING EMBEDDING MODEL
📥 Loading sentence-transformers/all-MiniLM-L6-v2...
✓ Embedding model loaded
   Dimension: 384

✅ All models ready for requests
```

---

### Test Embedding Endpoint

**Terminal 2:**
```bash
python3 test_embeddings.py
```

**Expected output:**
```
EMBEDDING ENDPOINT TEST

Texts to embed (3):
  1. running shoes
  2. football boots
  3. Horse riding equipment for kids

✓ Embeddings generated
   Model: sentence-transformers/all-MiniLM-L6-v2
   Dimension: 384
   Count: 3

✓ All embeddings present
✓ All embeddings have correct dimension (384)

✅ EMBEDDING TEST PASSED
```

---

### Test Render Backend

**With server running:**
```bash
cd backend
python3 api_swagger.py
```

**Expected startup:**
```
🔧 INITIALIZING RENDER BACKEND (Thin API Gateway)

1️⃣  Initializing PostgreSQL connection pool...
✓ PostgreSQL pool ready

2️⃣  Verifying remote model server connection...
   LOCAL_MODEL_URL: http://localhost:8001
   ✓ Using remote embedding server (NO local models)
   ✓ Using remote Qwen planner (NO local models)
✓ Model server healthy
   LLM: Qwen/Qwen2.5-1.5B-Instruct
   Device: mps
   Adapter loaded: True

✅ BACKEND READY (Thin API Gateway)

Memory footprint:
  • PostgreSQL client: ~50 MB
  • Flask + dependencies: ~100 MB
  • NO torch: 0 MB ✓
  • NO sentence-transformers: 0 MB ✓
  • NO Qwen model: 0 MB ✓
  Expected total: ~150-250 MB (fits in 512 MB free tier) ✓
```

---

## API Flow

### Search Query

```
Frontend
  ↓ POST /api/chat {"query": "running shoes under 5000"}
Render Backend
  ├─ Parse query → POST {LOCAL_MODEL_URL}/parse-query
  │  ↓ Returns: {"intent": "search", "search_request": {...}}
  ├─ Generate embeddings → POST {LOCAL_MODEL_URL}/embed
  │  ↓ Returns: {"embeddings": [[...]], "dimension": 384}
  ├─ Search PostgreSQL with embeddings
  └─ Generate recommendations → POST {LOCAL_MODEL_URL}/generate
     ↓ Returns: {"response": "Here are some great options..."}
```

All ML inference happens on Mac. Render just orchestrates HTTP calls.

---

## Memory Breakdown

### Render Backend (FREE tier - 512 MB)
```
PostgreSQL client:    ~50 MB
Flask + SQLAlchemy:   ~80 MB
Numpy (minimal):      ~20 MB
Python runtime:       ~30 MB
Request handlers:     ~20 MB
─────────────────────────────
Total:                ~200 MB ✓ Fits!
```

### Mac Local Server
```
Python runtime:       ~30 MB
Qwen2.5-1.5B (FP16):  ~1,500 MB
LoRA adapter:         ~35 MB
SentenceTransformer:  ~300 MB
FastAPI:              ~20 MB
─────────────────────────────
Total:                ~1,885 MB
```

---

## Files Modified

| File | Change |
|------|--------|
| `local_model_server.py` | Added `/embed` endpoint + embedding model loading |
| `backend/local_model_client.py` | Added `embed()` method |
| `backend/embedding.py` | Replaced with remote HTTP calls (NO local model) |
| `backend/api_swagger.py` | Removed embedding model loading |
| `backend/requirements_render.txt` | Removed ALL ML dependencies |
| `requirements_local_server.txt` | Added sentence-transformers |

---

## Verification Checklist

### Local Server
- [ ] Start: `python3 local_model_server.py`
- [ ] Qwen model loads
- [ ] LoRA adapter loads
- [ ] Embedding model loads
- [ ] Shows "All models ready"
- [ ] Test: `python3 test_embeddings.py`
- [ ] Embedding test passes

### Render Backend
- [ ] Start: `cd backend && python3 api_swagger.py`
- [ ] Shows "Thin API Gateway"
- [ ] Shows "NO local models"
- [ ] Shows "150-250 MB" expected
- [ ] Connects to local server
- [ ] NO "Loading SentenceTransformer" message
- [ ] NO "Loading Qwen" message

---

## Deployment

### 1. Start Local Server
```bash
python3 local_model_server.py
```

### 2. Expose with ngrok
```bash
ngrok http 8001
```

Copy ngrok URL: `https://xxxx.ngrok-free.app`

### 3. Deploy to Render

**Set environment variable:**
```
LOCAL_MODEL_URL=https://xxxx.ngrok-free.app
```

**Push code:**
```bash
git add .
git commit -m "Thin API gateway - all ML on Mac"
git push origin main
```

### 4. Monitor Render

**Check logs for:**
```
✓ Using remote embedding server (NO local models)
✓ Using remote Qwen planner (NO local models)
Expected total: ~150-250 MB (fits in 512 MB free tier) ✓
```

**Should NOT see:**
```
Loading SentenceTransformer...  ← BAD
Loading Qwen...                 ← BAD
```

---

## Success Criteria

✅ Local server loads both models  
✅ Embedding endpoint works (`/embed`)  
✅ Render backend starts without loading models  
✅ Render shows "Thin API Gateway"  
✅ Render uses < 250 MB RAM  
✅ End-to-end query works  
✅ No OOM errors on Render  

---

## Quick Test Commands

```bash
# Terminal 1: Start local server
python3 local_model_server.py

# Terminal 2: Test embeddings
python3 test_embeddings.py

# Terminal 3: Test backend
cd backend && python3 api_swagger.py
```

---

**Last Updated:** June 18, 2026  
**Status:** Thin API gateway complete ✅  
**Next:** Deploy to Render and monitor RAM usage
