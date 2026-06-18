# Project Standardization Complete ✓

## Status: Complete

The project has been standardized to use **Qwen2.5-3B-Instruct** across all components.

## Production Configuration

### Base Model
- **Model**: `Qwen/Qwen2.5-3B-Instruct`
- **Framework**: HuggingFace Transformers + PEFT
- **LoRA Adapter**: `training/outputs/qwen25_3b_instruct_lora_hf/`
- **LoRA Rank**: 8
- **LoRA Alpha**: 160

### Architecture
```
User Query
    ↓
Qwen2.5-3B-Instruct + LoRA
    ↓
Structured JSON (sport, category, keywords, price_limit)
    ↓
Hybrid Search (Keyword + Semantic)
    ↓
all-MiniLM-L6-v2 embeddings + PostgreSQL pgvector
    ↓
Retrieved Products
    ↓
Qwen2.5-3B-Instruct generates recommendations
    ↓
Natural Language Response
```

## Updated Files

### Backend
- ✓ `backend/hf_planner.py` - Updated to use Qwen2.5-3B-Instruct
- ✓ `backend/api_swagger.py` - Reverted to HuggingFace planner (removed Ollama references)
- ✓ `backend/.env` - Added HF_BASE_MODEL_NAME and HF_ADAPTER_PATH

### Training
- ✓ `training/train_hf.py` - Updated to train Qwen2.5-3B-Instruct
- ✓ `training/outputs/qwen25_3b_instruct_lora_hf/` - **PRODUCTION ADAPTER** (preserved)

### Deployment
- ✓ `docker-compose.yml` - Updated environment variables

## Archived Files

All experimental code has been moved to `training/archived_experiments/`:

### Ollama Experiments
- `training/archived_experiments/ollama/ollama_parser.py`
- `training/archived_experiments/ollama/test_parser.py`

### Qwen3-4B Experiments  
- `training/archived_experiments/qwen3/test_qwen.py`

### MLX Conversion Experiments
- `training/archived_experiments/mlx_conversion/convert_mlx_to_hf.py`
- `training/archived_experiments/mlx_conversion/shopping_agent_lora/`
- `training/archived_experiments/mlx_conversion/shopping_agent_lora_hf/`

### Documentation
- `archived_documentation/OLLAMA_ARCHITECTURE.md`
- `archived_documentation/MIGRATION_TO_OLLAMA.md`

## Commands

### Start API Locally
```bash
cd backend
python3 api_swagger.py
```

### Retrain Model
```bash
cd training
python3 train_hf.py
```

### Deploy with Docker
```bash
docker-compose up --build
```

## Environment Variables

### Required for Local Development
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=test

# API
API_KEY=decathlon_smart_search_2024_secure_key_abc123xyz

# Model
HF_BASE_MODEL_NAME=Qwen/Qwen2.5-3B-Instruct
HF_ADAPTER_PATH=../training/outputs/qwen25_3b_instruct_lora_hf
USE_HF_PLANNER=true
PRELOAD_MODEL=true
```

### Required for Render Deployment
```bash
# Database (from Render PostgreSQL)
POSTGRES_HOST=<render-postgres-host>
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=<render-user>
POSTGRES_PASSWORD=<render-password>

# API
API_KEY=<secure-api-key>

# Model
HF_BASE_MODEL_NAME=Qwen/Qwen2.5-3B-Instruct
HF_ADAPTER_PATH=/app/training/outputs/qwen25_3b_instruct_lora_hf
USE_HF_PLANNER=true
PRELOAD_MODEL=false  # Avoid timeout on startup
```

## What Was Removed

### From Production Path
- ❌ Ollama parser (zero-shot approach)
- ❌ Qwen3-4B references (switched to Qwen2.5-3B-Instruct)
- ❌ MLX training path (kept for local experimentation but not production)
- ❌ MLX to HuggingFace conversion (no longer needed)

### What Was Kept
- ✓ HuggingFace Transformers + PEFT
- ✓ Qwen2.5-3B-Instruct fine-tuned adapter
- ✓ Hybrid search (keyword + semantic)
- ✓ all-MiniLM-L6-v2 embeddings
- ✓ PostgreSQL + pgvector
- ✓ All product schemas and APIs

## Training Data
- Location: `training/data/train.jsonl`
- Updated with multi-category examples for running/football
- ~1000 examples covering various sports and queries

## Model Performance
- **Device**: Apple M5 MPS (GPU acceleration)
- **Inference Speed**: 20-40 seconds per query (with MPS)
- **Training Time**: ~1-2 hours for 1 epoch on M5 Air
- **Memory**: ~6-8GB RAM during inference

## Next Steps
1. Test API locally: `python3 backend/api_swagger.py`
2. Verify smart search endpoint with test queries
3. Deploy to Render with updated environment variables
4. Monitor performance and accuracy

## Notes
- All changes prioritize **Qwen2.5-3B-Instruct** (not Qwen3-4B)
- Experimental code archived (not deleted) for future reference
- Single clean production pipeline without mixed approaches
- Ready for deployment with standardized configuration
