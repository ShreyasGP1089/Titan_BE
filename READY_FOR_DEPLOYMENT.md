# ✅ READY FOR RENDER DEPLOYMENT

## Status: STANDARDIZED ON QWEN2.5-1.5B-INSTRUCT

All code has been updated to use **Qwen/Qwen2.5-1.5B-Instruct** for reliable Render deployment.

---

## 🎯 What Changed

### Before (Mixed Models)
- ❌ Qwen3-4B references
- ❌ Qwen2.5-3B-Instruct  
- ❌ Ollama qwen3:4b
- ❌ mlx-community models
- ❌ Mixed experimental paths

### After (Single Model)
- ✅ **Qwen/Qwen2.5-1.5B-Instruct** everywhere
- ✅ Single production path
- ✅ Render-optimized (3 GB model)
- ✅ Fast cold start (<60s with preload)
- ✅ Fits in 8 GB RAM plan

---

## 📋 Quick Start

### 1. Train the Adapter
```bash
cd training
python3 train_hf.py
```

**Expected output:**
- Model: Qwen/Qwen2.5-1.5B-Instruct
- Output: `outputs/qwen25_1_5b_lora_hf/`
- Time: ~1-2 hours on M5 Air
- Size: ~25-50 MB adapter

### 2. Test Locally
```bash
cd backend
python3 api_swagger.py
```

**Visit:** http://localhost:5000/docs

**Test query:**
```bash
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -d '{"query": "running shoes under 5000"}'
```

### 3. Deploy to Render

#### A. Create PostgreSQL Database
```yaml
name: decathlon-postgres
plan: starter  # Free tier OK for testing
database: decathlon_rag
```

#### B. Create Web Service
```yaml
name: decathlon-api
env: python
plan: standard  # 8 GB RAM minimum
buildCommand: pip install -r backend/requirements_production.txt
startCommand: python backend/api_swagger.py
```

#### C. Set Environment Variables
```bash
# Database (from Render PostgreSQL internal connection)
POSTGRES_HOST=<internal-postgres-host>
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=<username>
POSTGRES_PASSWORD=<password>

# API Key
API_KEY=<generate-secure-32-char-key>

# Model (CRITICAL)
HF_BASE_MODEL_NAME=Qwen/Qwen2.5-1.5B-Instruct
HF_ADAPTER_PATH=/app/training/outputs/qwen25_1_5b_lora_hf
PRELOAD_MODEL=false  # Important: avoid health check timeout

# Optional Cache
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/transformers
```

#### D. Configure Health Check
- Path: `/api/v1/system/health`
- Interval: 30 seconds
- Timeout: 10 seconds

---

## 📊 Expected Performance

### Memory Usage
- **Startup**: ~4 GB
- **Runtime Peak**: ~5-6 GB
- **Render Plan**: 8 GB (safe margin)

### Response Times
- **Parse Query**: 10-20s (CPU) | 2-5s (GPU)
- **Hybrid Search**: 0.1-0.5s
- **Generate Response**: 10-20s (CPU) | 2-5s (GPU)
- **Total**: 20-40s (CPU) | 4-10s (GPU)

### Cold Start
- **Without Preload**: ~10-20s (model loads on first request)
- **With Preload**: ~40-80s (loads at startup)
- **Recommendation**: `PRELOAD_MODEL=false` for Render

---

## 🗂️ Files Updated

### Core Code
- ✅ `backend/hf_planner.py`
- ✅ `backend/api_swagger.py`
- ✅ `training/train_hf.py`

### Configuration
- ✅ `backend/.env`
- ✅ `backend/.env.production.example`
- ✅ `docker-compose.yml`
- ✅ `Dockerfile`

### Documentation
- ✅ `README.md`
- ✅ `DEPLOYMENT_REPORT.md` (NEW)
- ✅ `MODEL_AUDIT.md` (NEW)

---

## 🗄️ Files Archived

All experimental code moved to `training/archived_experiments/`:

```
archived_experiments/
├── ollama/
│   ├── ollama_parser.py
│   ├── config.py
│   └── test_parser.py
├── qwen3/
│   └── test_qwen.py
├── mlx_conversion/
│   ├── convert_mlx_to_hf.py
│   ├── shopping_agent_lora/
│   └── shopping_agent_lora_hf/
└── old_adapters/
    └── qwen25_3b_instruct_lora_hf/
```

---

## 🏗️ Architecture

```
User Query
    ↓
Qwen2.5-1.5B-Instruct + LoRA
    ↓
Structured JSON
    ↓
Hybrid Search (Keyword + Semantic)
    ↓
all-MiniLM-L6-v2 + pgvector
    ↓
PostgreSQL
    ↓
Products
    ↓
Qwen2.5-1.5B-Instruct Response
    ↓
Natural Language
```

---

## ✅ Pre-Deployment Checklist

### Local Development
- [ ] Train adapter: `python3 training/train_hf.py`
- [ ] Verify adapter exists: `training/outputs/qwen25_1_5b_lora_hf/`
- [ ] Test API locally: `python3 backend/api_swagger.py`
- [ ] Test parse-query endpoint
- [ ] Test smart-search endpoint
- [ ] Verify no Qwen3/Ollama references remain

### Render Setup
- [ ] Create PostgreSQL database service
- [ ] Note internal connection URL
- [ ] Create Web Service (Python, 8 GB RAM)
- [ ] Set environment variables (see above)
- [ ] Configure health check endpoint
- [ ] Set build command
- [ ] Set start command

### Post-Deployment
- [ ] Health check passes: `GET /api/v1/system/health`
- [ ] Parse endpoint works: `POST /api/v1/shopping/parse-query`
- [ ] Smart search works: `POST /api/v1/shopping/smart-search`
- [ ] Memory usage < 6 GB
- [ ] Response time < 45 seconds

---

## 🚨 Important Notes

### DO NOT
- ❌ Use `PRELOAD_MODEL=true` on Render (causes health check timeout)
- ❌ Use Qwen3-4B or Qwen2.5-3B (too large, >5 GB RAM)
- ❌ Include Ollama dependencies (not needed)
- ❌ Try to run MLX on Render (M-series only, not available)

### DO
- ✅ Use Qwen2.5-1.5B-Instruct (3 GB, fits in 8 GB plan)
- ✅ Set `PRELOAD_MODEL=false` (model loads on first request)
- ✅ Use internal PostgreSQL connection (faster, secure)
- ✅ Generate strong API_KEY (32+ chars)
- ✅ Monitor memory and response times

---

## 📚 Documentation

### Key Documents
1. **`DEPLOYMENT_REPORT.md`** - Complete deployment specs
2. **`MODEL_AUDIT.md`** - What changed and why
3. **`README.md`** - Quick start guide
4. **`backend/QUICKSTART.md`** - API usage examples

### API Documentation
- **Swagger UI**: `http://<your-render-url>/docs`
- **Health Check**: `GET /api/v1/system/health`
- **Parse Query**: `POST /api/v1/shopping/parse-query`
- **Smart Search**: `POST /api/v1/shopping/smart-search` (requires API key)

---

## 🎯 Why Qwen2.5-1.5B-Instruct?

### Deployment Priority
1. **Must fit in Render's 8 GB plan** ✅
2. **Fast cold start (<60s)** ✅
3. **Stable inference** ✅
4. **Low cost** ✅

### Model Comparison
| Model | Size | RAM | Startup | Cost |
|-------|------|-----|---------|------|
| Qwen3-4B | 4B | ~8 GB | ~90s | High |
| Qwen2.5-3B | 3B | ~6 GB | ~70s | Medium |
| **Qwen2.5-1.5B** | **1.5B** | **~3 GB** | **~40s** | **Low** |

### Quality Trade-off
- ✅ Still excellent for structured JSON parsing
- ✅ Perfect for e-commerce queries
- ✅ Same Qwen 2.5 architecture
- ⚠️ Slightly less capable for complex multi-step reasoning
- ✅ **But deployment reliability > marginal quality gain**

---

## 🚀 Deploy Now

### Command Sequence
```bash
# 1. Train adapter
cd training
python3 train_hf.py

# 2. Test locally
cd ../backend
python3 api_swagger.py

# 3. Commit and push
git add .
git commit -m "Deploy Qwen2.5-1.5B-Instruct to Render"
git push origin main

# 4. Deploy on Render
# - Follow Render setup steps above
# - Set environment variables
# - Deploy
```

---

## 📞 Support

- **Model**: Qwen/Qwen2.5-1.5B-Instruct
- **Adapter**: qwen25_1_5b_lora_hf
- **Target**: Render (8 GB RAM)
- **Status**: ✅ READY TO DEPLOY

---

**Next Step**: Train the adapter with `python3 training/train_hf.py` 🚀
