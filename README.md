# Decathlon Smart Search System

> **Fine-tuned Qwen2.5-1.5B-Instruct + Hybrid Search + PostgreSQL + pgvector**

Complete AI-powered conversational commerce backend for e-commerce product search.

## 🎯 What This Is

- **Fine-tuned LLM** (Qwen2.5-1.5B-Instruct with LoRA) for query understanding
- **Hybrid Search** (Keyword filtering + Semantic ranking with pgvector)
- **Vector Database** (PostgreSQL with 8,829 products)
- **REST API** (Flask + Swagger documentation)

## 🚀 Quick Start

```bash
# Start API
cd backend
python3 api_swagger.py

# Test API
python3 test_smart_search_fixed.py

# Open Swagger UI
open http://localhost:5000/docs
```

## 📡 Three API Endpoints

| Endpoint | Purpose | Speed | Use When |
|----------|---------|-------|----------|
| `/parse-query` | Natural language → JSON | ~500ms | Testing, custom integration |
| `/hybrid-search` | JSON → Products | ~100ms | Fast search |
| `/smart-search` | Natural language → Complete response | ~1-2s | End users |

### Quick Examples

```bash
# Parse query (get JSON)
curl -X POST http://localhost:5000/api/v1/shopping/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "football cleats under 5000"}'

# Search with JSON
curl -X POST http://localhost:5000/api/v1/shopping/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{"parsed_query": {"intent": "search", "search_request": {...}}}'

# Complete pipeline
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -d '{"query": "football cleats under 5000"}'
```

## 📚 Documentation

- **API_GUIDE.md** - Complete API reference with examples
- **Swagger UI** - http://localhost:5000/docs (interactive testing)

## 🏗️ Architecture

```
User Query → Fine-tuned Qwen 3:4B → Structured JSON
    → Keyword Filter (SQL) → Semantic Rank (pgvector)
    → Qwen Re-ranking → Products + Recommendations
```

**Tech Stack**: Python 3.11+, PostgreSQL + pgvector, Apple MLX, Flask, Qwen 3:4B

## 📁 Project Structure

```
Toolset/
├── backend/              # API and search logic
│   ├── api_swagger.py           # Main API
│   ├── mlx_planner.py           # MLX integration
│   ├── search_pipeline.py       # Hybrid search
│   ├── db.py                    # Database
│   └── test_*.py                # Tests
├── training/             # Model training
│   ├── train_mlx.py             # Training script
│   ├── inference_mlx.py         # Testing script
│   └── outputs/                 # Fine-tuned model
└── API_GUIDE.md          # Complete documentation
```

## ⚠️ Important: Chaining Endpoints

When using `/parse-query` → `/hybrid-search`:

```python
# ✅ CORRECT
response = requests.post("/parse-query", json={"query": "..."}).json()
parsed_query = response['parsed_query']  # Extract only this!
requests.post("/hybrid-search", json={"parsed_query": parsed_query})

# ❌ WRONG - Don't pass entire response
requests.post("/hybrid-search", json=response)  # FAILS!
```

See **API_GUIDE.md** for detailed examples.

## 🧪 Testing

```bash
cd backend

# Test all endpoints
python3 test_smart_search_fixed.py

# Test parse-query only
python3 test_parse_query.py

# Test model separately (no API)
cd ../training
python3 inference_mlx.py
```

## 📈 Performance

- **Parse**: ~500ms (MLX inference)
- **Search**: ~100ms (hybrid keyword + semantic)
- **Complete**: ~1-2s (parse + search + recommendations)

## 🔧 Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- Apple Silicon Mac (for MLX)
- 8GB+ RAM

## 📊 Database

```bash
# Check database
psql -U decathlonuser -d decathlon_db -c "SELECT COUNT(*) FROM products;"
# Should return: 8829

psql -U decathlonuser -d decathlon_db -c "SELECT COUNT(*) FROM product_embeddings;"
# Should return: 8829
```

## 🐛 Troubleshooting

### API won't start?
```bash
lsof -i :5000  # Check if port is in use
```

### Model not found?
```bash
cd training
python3 train_mlx.py  # Train the model (~30-45 min)
```

### Test model only?
```bash
cd training
python3 inference_mlx.py  # Test without API/database
```

## ✅ What's Working

- ✅ Fine-tuned model (Qwen 3:4B + LoRA, 89% loss reduction)
- ✅ Hybrid search (keyword + semantic ranking)
- ✅ 3 API endpoints operational
- ✅ Model pre-loads on startup (no cold start)
- ✅ 8,829 products indexed with embeddings
- ✅ Complete documentation + test suites

## 📖 Learn More

- **Complete API Guide**: See `API_GUIDE.md`
- **Interactive Docs**: http://localhost:5000/docs
- **Training Guide**: `training/MLX_TRAINING_GUIDE.md`
- **Backend Setup**: `backend/QUICKSTART.md`

---

**Ready to use!** Start with: `cd backend && python3 api_swagger.py`
