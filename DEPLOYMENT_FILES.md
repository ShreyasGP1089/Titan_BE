# 📦 Production Deployment File Structure

**Essential files for Railway / Render deployment**

---

## 🎯 Minimal Production Structure

```
Toolset/
├── 📄 Dockerfile                           # Container build configuration
├── 📄 docker-compose.yml                   # Local testing setup
├── 📄 README.md                            # Project overview
├── 📄 DEPLOY_NOW.md                        # Deployment instructions
├── 📄 DEPLOYMENT_ARCHITECTURE.md           # Architecture documentation
├── 📄 .gitignore                           # Git ignore rules
│
├── 📁 backend/                             # Backend API code
│   ├── 📄 api_swagger.py                   # ⭐ Main Flask API (entry point)
│   ├── 📄 hf_planner.py                    # ⭐ AI planner (HuggingFace)
│   ├── 📄 search_pipeline.py               # ⭐ Hybrid search logic
│   ├── 📄 db.py                            # Database connection pool
│   ├── 📄 embedding.py                     # Sentence embeddings
│   ├── 📄 tools.py                         # Search helper functions
│   ├── 📄 config.py                        # Configuration management
│   ├── 📄 __init__.py                      # Python package marker
│   │
│   ├── 📄 requirements_production.txt      # ⭐ Production dependencies (Linux)
│   ├── 📄 .env.example                     # Environment template
│   │
│   └── 📁 Documentation/
│       ├── 📄 README.md                    # Backend overview
│       ├── 📄 ARCHITECTURE.md              # System architecture
│       └── 📄 API_CONNECTION_GUIDE.md      # API usage guide
│
└── 📁 training/
    └── 📁 outputs/
        └── 📁 shopping_agent_lora_hf/      # ⭐ Fine-tuned model adapter
            ├── 📄 adapter_model.safetensors # 25MB LoRA weights
            └── 📄 adapter_config.json       # PEFT configuration
```

---

## ⭐ Critical Files (MUST Include)

### 1. **Dockerfile**
- Container image build instructions
- Installs dependencies from `requirements_production.txt`
- Copies backend code and HF adapter
- Exposes port 5000

### 2. **backend/api_swagger.py**
- Main Flask application entry point
- REST API with Swagger documentation
- API key authentication
- Routes: `/api/v1/shopping/*`, `/docs`

### 3. **backend/hf_planner.py**
- Production AI planner using HuggingFace Transformers
- Loads Qwen 2.5 Coder 3B + LoRA adapter
- Parses natural language → structured JSON
- Supports CPU and GPU inference

### 4. **backend/search_pipeline.py**
- Hybrid search implementation
- Combines keyword filtering + semantic search
- PostgreSQL + pgvector integration

### 5. **backend/requirements_production.txt**
- All Python dependencies for Linux
- NO MLX packages (Mac-only)
- Includes: flask, transformers, peft, torch, psycopg2

### 6. **training/outputs/shopping_agent_lora_hf/**
- Fine-tuned LoRA adapter (25MB)
- PEFT format compatible with HuggingFace
- Required for smart search functionality

---

## 🗑️ Files Excluded (In .gitignore)

### Documentation (Redundant)
- ❌ `CLEANUP_SUMMARY.md`
- ❌ `IMPLEMENTATION_COMPLETE.txt`
- ❌ `REFACTORING_COMPLETE.md`
- ❌ `MIGRATION_SUMMARY.md`
- ❌ `DOCUMENTATION_INDEX.md`
- ❌ `DEPLOYMENT_README.md`
- ❌ `PRODUCTION_DEPLOYMENT.md`
- ❌ `PRODUCTION_READY.md`
- ❌ `READY_TO_DEPLOY.txt`
- ❌ `DEPLOYMENT_QUICK_REFERENCE.md`
- ❌ `API_GUIDE.md`

**Why:** Internal development docs not needed for deployment

### Backend Documentation (Redundant)
- ❌ `backend/QUICKSTART.md`
- ❌ `backend/SETUP.md`
- ❌ `backend/SUCCESS_GUIDE.md`
- ❌ `backend/SWAGGER_GUIDE.md`
- ❌ `backend/SWAGGER_QUICKSTART.txt`
- ❌ `backend/VISUAL_GUIDE.md`
- ❌ `backend/CONNECTION_TROUBLESHOOTING.md`
- ❌ `backend/DEPLOYMENT.md`
- ❌ `backend/OPENAPI_CONFIG.json`

**Why:** Swagger `/docs` provides interactive API documentation

### Scripts (Development/Testing)
- ❌ `verify_production_ready.sh`
- ❌ `quick_verify.sh`
- ❌ `deploy.sh`
- ❌ `backend/generate_cert.sh`
- ❌ `backend/example_client.html`

**Why:** Only needed during local development/verification

### Test Files
- ❌ `backend/test_*.py`
- ❌ `backend/*_test.py`

**Why:** Tests run in CI/CD, not needed in production container

### Backend (Development Only)
- ❌ `backend/mlx_planner.py` (Mac-only, not for Linux)
- ❌ `backend/api.py` (old API, replaced by api_swagger.py)
- ❌ `backend/main.py` (old entry point)
- ❌ `backend/qwen_client.py` (development client)
- ❌ `backend/planner.py` (old planner)

**Why:** Development/Mac-specific files not needed in production

### Training Files
- ❌ `training/*.py` (scripts)
- ❌ `training/*.md` (documentation)
- ❌ `training/data/` (datasets)
- ❌ `training/outputs/shopping_agent_lora/` (MLX adapter)

**Why:** Only converted HF adapter needed, not training code/data

### System Files
- ❌ `.DS_Store` (macOS)
- ❌ `__pycache__/` (Python cache)
- ❌ `.vscode/` (IDE settings)
- ❌ `.env` (secrets - never commit!)

**Why:** System files and secrets should never be in git

---

## 📊 File Size Summary

### Total Deployment Size: ~50MB

| Component | Size | Purpose |
|-----------|------|---------|
| Backend Python code | ~500KB | API and search logic |
| LoRA Adapter | ~25MB | Fine-tuned model weights |
| Dockerfile + configs | ~10KB | Deployment configuration |
| Documentation | ~100KB | README, deployment guides |
| **Total** | **~26MB** | **Actual deployment** |

**Note:** Base model (Qwen 2.5 Coder 3B ~6GB) downloads automatically on first run from HuggingFace.

---

## 🚀 What Gets Deployed

### Railway / Render Deploy
```bash
# These files are sent to the platform:
.
├── Dockerfile
├── docker-compose.yml (optional, for reference)
├── backend/
│   ├── *.py (API code)
│   ├── requirements_production.txt
│   └── .env.example
└── training/outputs/shopping_agent_lora_hf/
    ├── adapter_model.safetensors
    └── adapter_config.json
```

### What Gets Downloaded at Runtime
```
- Qwen/Qwen2.5-Coder-3B-Instruct (~6GB) - from HuggingFace
- BAAI/bge-small-en-v1.5 (~100MB) - sentence embeddings
```

**First deployment takes longer** (~5-10 min) as models download. Subsequent deploys are cached.

---

## 🔧 Environment Variables (Not Files)

These are set in Railway/Render dashboard, NOT in code:

```bash
USE_HF_PLANNER=true
API_KEY=your_secure_key
POSTGRES_HOST=your-db-host
POSTGRES_DB=decathlon_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
```

**Never commit `.env` to git!** Use `.env.example` as a template.

---

## ✅ Deployment Checklist

Before deploying, ensure:

- [x] `.gitignore` excludes unnecessary files
- [x] `.env` is NOT committed (check with `git status`)
- [x] HF adapter exists: `training/outputs/shopping_agent_lora_hf/`
- [x] `requirements_production.txt` has no MLX packages
- [x] `Dockerfile` uses `requirements_production.txt`
- [x] Documentation files are in `.gitignore`
- [ ] Push to GitHub: `git push origin main`
- [ ] Deploy to Railway/Render

---

## 📝 Git Commands

```bash
# Check what will be committed
git status

# Should NOT see:
# - .env
# - *.pyc, __pycache__/
# - test_*.py
# - Documentation files (CLEANUP_SUMMARY.md, etc.)
# - Scripts (verify_*.sh)

# Add essential files
git add Dockerfile docker-compose.yml README.md DEPLOY_NOW.md
git add backend/*.py backend/requirements_production.txt
git add training/outputs/shopping_agent_lora_hf/

# Commit
git commit -m "Production ready: Flask + HuggingFace + PEFT"

# Push
git push origin main
```

---

## 🎯 Essential vs. Optional

### ESSENTIAL (Must have for deployment)
✅ `Dockerfile`
✅ `backend/api_swagger.py`
✅ `backend/hf_planner.py`
✅ `backend/search_pipeline.py`
✅ `backend/requirements_production.txt`
✅ `training/outputs/shopping_agent_lora_hf/*.safetensors`

### RECOMMENDED (Helpful but optional)
📌 `README.md` - Project overview
📌 `DEPLOY_NOW.md` - Deployment guide
📌 `DEPLOYMENT_ARCHITECTURE.md` - Architecture docs
📌 `docker-compose.yml` - Local testing

### OPTIONAL (Can be ignored)
⚪ All other markdown files (redundant documentation)
⚪ Test files
⚪ Development scripts
⚪ MLX files

---

## 🔗 Related Files

- **`.gitignore`** - Complete list of excluded files
- **`DEPLOY_NOW.md`** - Step-by-step deployment guide
- **`DEPLOYMENT_ARCHITECTURE.md`** - System architecture
- **`README.md`** - Project overview

---

**Last Updated:** June 17, 2026  
**Status:** Production Ready ✅  
**Deployment Size:** ~26MB (excluding base model)
