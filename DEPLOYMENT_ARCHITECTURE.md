# 🏗️ Production Deployment Architecture

**Target Platforms:** Railway, Render, AWS, DigitalOcean, or any Linux cloud  
**Stack:** Flask + HuggingFace Transformers + PEFT + PostgreSQL + pgvector

---

## 📊 Production Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT APPLICATIONS                      │
│  (Mobile App, Web Frontend, Third-party Services)           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTPS + API-KEY
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              BACKEND API (Railway / Render)                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                   Flask API Server                       │ │
│ │                  (api_swagger.py)                        │ │
│ │  • REST API with Swagger documentation                   │ │
│ │  • API key authentication                                │ │
│ │  • CORS enabled for web clients                          │ │
│ │  • Health checks & monitoring                            │ │
│ └────────────────────┬────────────────────────────────────┘ │
│                      │                                       │
│                      ▼                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │           AI Planner (hf_planner.py)                    │ │
│ │  ┌────────────────────────────────────────────────┐     │ │
│ │  │  HuggingFace Transformers + PEFT              │     │ │
│ │  │  • Base: Qwen/Qwen2.5-Coder-3B-Instruct      │     │ │
│ │  │  • LoRA Adapter: 25MB (shopping_agent)        │     │ │
│ │  │  • 8-bit quantization on GPU                  │     │ │
│ │  │  • Full precision on CPU                      │     │ │
│ │  │  • Model preloaded at startup (~20s)          │     │ │
│ │  └────────────────────────────────────────────────┘     │ │
│ │                                                           │ │
│ │  Flow:                                                    │ │
│ │  User Query → Fine-tuned Qwen → Structured JSON          │ │
│ └────────────────────┬────────────────────────────────────┘ │
│                      │                                       │
│                      ▼                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │         Hybrid Search Pipeline                           │ │
│ │  • Keyword filtering (sport, category, price)            │ │
│ │  • Semantic search with embeddings (384d)                │ │
│ │  • HNSW index for fast similarity                        │ │
│ └────────────────────┬────────────────────────────────────┘ │
└────────────────────────┼────────────────────────────────────┘
                         │
                         │ SQL + Vector Queries
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         PostgreSQL + pgvector (Managed Database)             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  Products Table                                          │ │
│ │  • 8,829 Decathlon products                              │ │
│ │  • Full product metadata (name, price, category, etc.)   │ │
│ │  • 384-dimensional embedding vectors                     │ │
│ │  • HNSW index for ~80ms semantic search                  │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Component Breakdown

### 1. Flask API Server (`backend/api_swagger.py`)

**Technology:** Flask + Flask-RESTX  
**Port:** 5000  
**Features:**
- REST API with OpenAPI/Swagger documentation
- API key authentication (header: `API-KEY`)
- CORS enabled for cross-origin requests
- Health check endpoint: `/api/v1/system/health`
- Auto-documentation at `/docs`

**Key Endpoints:**
```
POST /api/v1/shopping/smart-search    # Complete AI-powered search
POST /api/v1/shopping/parse-query     # Parse query to JSON only
POST /api/v1/shopping/hybrid-search   # Search with parsed JSON
POST /api/v1/shopping/search          # Simple semantic search
GET  /api/v1/products/categories      # List all categories
POST /api/v1/products/compare         # Compare products
GET  /api/v1/system/health            # Health check
```

**Environment Variables:**
- `USE_HF_PLANNER=true` - Use HuggingFace planner (production)
- `API_KEY` - API authentication key
- `POSTGRES_*` - Database connection details

---

### 2. AI Planner (`backend/hf_planner.py`)

**Technology:** HuggingFace Transformers + PEFT  
**Model:** Qwen/Qwen2.5-Coder-3B-Instruct (3 Billion parameters)  
**Adapter:** LoRA (25MB) trained on 1,500 e-commerce queries

**How It Works:**
```python
User Query: "Horse riding boots for kids below 3000"
     ↓
Fine-tuned Qwen (with LoRA adapter)
     ↓
Structured JSON:
{
  "intent": "search",
  "search_request": {
    "sport": "Horse Riding",
    "category": "Riding Boots",
    "keywords": ["boots", "kids"],
    "price_limit": 3000,
    "experience_level": null
  }
}
```

**Hardware Support:**
- **CPU:** Full precision (FP32), 1-3 seconds per query
- **GPU:** 8-bit quantization (bitsandbytes), 0.5-1 second per query
- **Memory:** 4-8GB RAM recommended

**Model Loading:**
- Preloaded at API startup (~10-20 seconds)
- Cached in memory for fast inference
- Automatic device detection (CUDA/CPU)

---

### 3. Hybrid Search Pipeline (`backend/search_pipeline.py`)

**Technology:** PostgreSQL + pgvector + Sentence Transformers  
**Embedding Model:** BAAI/bge-small-en-v1.5 (384 dimensions)

**Search Flow:**
```
Structured JSON from Qwen
     ↓
1. Keyword Filtering (SQL WHERE clauses)
   - Sport category
   - Category levels 1 & 2
   - Price limit
   - Experience level
     ↓
2. Semantic Search (pgvector similarity)
   - Convert keywords to 384d embedding
   - Cosine similarity search
   - HNSW index for speed (~80ms)
     ↓
3. Return Top K Products (default: 10)
   - Sorted by similarity score
   - Complete product metadata
```

**Performance:**
- Keyword filtering: ~10ms
- Semantic search: ~80ms (with HNSW index)
- Total: ~100ms per search

---

### 4. PostgreSQL + pgvector Database

**Technology:** PostgreSQL 15+ with pgvector extension  
**Managed Options:**
- Railway (PostgreSQL plugin - automatic)
- Render (PostgreSQL service)
- AWS RDS (manual pgvector setup)
- DigitalOcean Managed Database
- Supabase (PostgreSQL with pgvector)

**Schema:**
```sql
CREATE TABLE products (
    product_id VARCHAR PRIMARY KEY,
    name TEXT,
    brand VARCHAR,
    price NUMERIC,
    mrp NUMERIC,
    sport VARCHAR,
    category_level_1 VARCHAR,
    category_level_2 VARCHAR,
    description TEXT,
    image_url TEXT,
    product_url TEXT,
    rating NUMERIC,
    review_count INTEGER,
    experience_level VARCHAR,
    embedding vector(384)  -- pgvector column
);

-- HNSW index for fast similarity search
CREATE INDEX ON products 
USING hnsw (embedding vector_cosine_ops);
```

**Data:**
- 8,829 Decathlon products
- 26 sports categories
- ~100 subcategories
- Pre-computed embeddings

---

## 🚀 Deployment Options

### Option 1: Railway (Recommended - Easiest)

**Why Railway?**
- ✅ Automatic PostgreSQL provisioning with pgvector
- ✅ Zero-config Docker deployment
- ✅ Auto-scaling
- ✅ Free tier available ($5/month credit)
- ✅ Built-in monitoring

**Architecture:**
```
Railway Project
├── Backend Service (Dockerfile)
│   ├── Environment: USE_HF_PLANNER=true
│   ├── Port: 5000
│   └── Public URL: https://your-app.railway.app
└── PostgreSQL Plugin
    ├── pgvector extension (auto-installed)
    └── Connection string (auto-injected)
```

**Deploy:**
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
railway init

# 4. Add PostgreSQL
railway add --plugin postgresql

# 5. Deploy
railway up

# Done! Railway will:
# - Build your Dockerfile
# - Set up PostgreSQL with pgvector
# - Generate public URL
# - Handle SSL certificates
```

---

### Option 2: Render (Docker-Native)

**Why Render?**
- ✅ Native Docker support
- ✅ Managed PostgreSQL
- ✅ Automatic SSL
- ✅ GitHub integration
- ✅ Free tier available

**Architecture:**
```
Render Project
├── Web Service (Docker)
│   ├── Build: Dockerfile
│   ├── Environment Variables
│   └── Public URL: https://your-app.onrender.com
└── PostgreSQL Service
    ├── Version: 15+
    └── Connection string
```

**Deploy:**
1. Push code to GitHub
2. Connect Render to repository
3. Create PostgreSQL service first
4. Create Web Service (Docker)
5. Link PostgreSQL to Web Service
6. Set environment variables
7. Deploy!

See `DEPLOY_NOW.md` for detailed steps.

---

### Option 3: AWS EC2 / DigitalOcean (Full Control)

**Why AWS/DO?**
- ✅ Full server control
- ✅ Custom instance sizing
- ✅ Private networking
- ✅ Existing infrastructure integration

**Architecture:**
```
Linux Server (Ubuntu 22.04)
├── Docker
│   ├── docker-compose.yml
│   ├── PostgreSQL container (pgvector)
│   └── API container (Dockerfile)
├── Nginx (optional reverse proxy)
└── SSL (Let's Encrypt)
```

**Deploy:**
```bash
# 1. Clone repo
git clone <your-repo>

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit with production credentials

# 3. Start with Docker Compose
docker-compose up -d

# 4. Load product data
docker exec -it decathlon_api python load_data.py
```

See `DEPLOY_NOW.md` for full instructions.

---

## 📊 Resource Requirements

### Minimum (CPU-only)
- **CPU:** 2 cores
- **RAM:** 4GB
- **Storage:** 10GB
- **Performance:** 1-3 seconds per query

### Recommended (CPU)
- **CPU:** 4 cores
- **RAM:** 8GB
- **Storage:** 20GB
- **Performance:** 1-2 seconds per query

### Optimal (GPU)
- **CPU:** 4 cores
- **RAM:** 8GB
- **Storage:** 20GB
- **GPU:** NVIDIA T4 or better (8GB VRAM)
- **Performance:** 0.5-1 second per query

### Database
- **PostgreSQL:** 2GB RAM minimum
- **Storage:** 5GB minimum (includes vectors)
- **Connections:** 20-100 concurrent

---

## 🔐 Security Configuration

### API Authentication
```python
# Required header for smart-search endpoint
API-KEY: your_secure_key_here
```

**Best Practices:**
1. Change default API key in production
2. Use strong, random keys (32+ characters)
3. Rotate keys periodically
4. Store keys in environment variables (never in code)
5. Consider rate limiting for public APIs

### Database Security
1. Use strong passwords
2. Enable SSL connections
3. Restrict IP access (firewall rules)
4. Regular backups
5. Use managed database services when possible

### HTTPS/SSL
- Railway: Automatic SSL ✅
- Render: Automatic SSL ✅
- Custom server: Use Let's Encrypt + Certbot

---

## 📈 Monitoring & Logging

### Health Checks
```bash
# Check if API is running
curl https://your-api.railway.app/api/v1/system/health

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "model": "loaded"
}
```

### Logging
```python
# Application logs include:
- Request/response times
- Model inference times
- Search query performance
- Database query performance
- Errors and stack traces
```

### Metrics to Monitor
- **API Response Time:** Target <2 seconds
- **Model Inference Time:** Target <1 second
- **Database Query Time:** Target <100ms
- **Error Rate:** Target <1%
- **Memory Usage:** Should be stable (no leaks)

---

## 🔄 CI/CD Pipeline (Optional)

### GitHub Actions Example
```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Railway
        run: |
          npm install -g @railway/cli
          railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

---

## 📋 Environment Variables Reference

### Required for Production
```bash
# Planner Configuration
USE_HF_PLANNER=true                    # Use HuggingFace (not MLX)

# Database
POSTGRES_HOST=your-db-host.railway.app
POSTGRES_PORT=5432
POSTGRES_DB=railway
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# API Security
API_KEY=your_secure_api_key_here       # Change this!

# Optional: Model Cache
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/transformers
```

---

## 🎯 Performance Optimization

### 1. Model Loading
- **Problem:** First request takes 10-20 seconds
- **Solution:** Model preloads at startup (already implemented)

### 2. Database Queries
- **Problem:** Slow semantic search
- **Solution:** HNSW index on embedding column (already implemented)

### 3. Response Time
- **Current:** 1-2 seconds (CPU), 0.5-1 second (GPU)
- **Optimization:** Use GPU instance or model serving (vLLM, TGI)

### 4. Concurrent Requests
- **Current:** Flask dev server (single-threaded)
- **Production:** Use Gunicorn with 4-8 workers
  ```bash
  gunicorn -w 4 -b 0.0.0.0:5000 api_swagger:app
  ```

### 5. Caching (Future Enhancement)
```python
# Add Redis for frequent queries
redis_cache = {
    "running shoes under 5000": cached_result,
    ...
}
```

---

## ✅ Deployment Checklist

Before deploying:

- [ ] Environment variable `USE_HF_PLANNER=true` is set
- [ ] API key is changed from default
- [ ] Database credentials are secure
- [ ] PostgreSQL has pgvector extension installed
- [ ] Product data is loaded in database
- [ ] Health endpoint responds: `/api/v1/system/health`
- [ ] Model preloads successfully at startup
- [ ] Test query returns products
- [ ] SSL/HTTPS is enabled (automatic on Railway/Render)
- [ ] Monitoring/logging is configured

---

## 🆘 Troubleshooting

### Model Loading Fails
```
Error: Can't load adapter from training/outputs/shopping_agent_lora_hf
```
**Solution:** Ensure adapter is included in Docker build:
```dockerfile
COPY training/outputs/shopping_agent_lora_hf/ ./training/outputs/shopping_agent_lora_hf/
```

### Database Connection Fails
```
Error: could not connect to server
```
**Solution:** Check environment variables and firewall rules

### Slow Inference
```
Query takes 5+ seconds
```
**Solution:** 
1. Check if model preloaded (logs should show "Model loaded")
2. Consider GPU instance
3. Reduce `max_new_tokens` in `hf_planner.py`

### Out of Memory
```
CUDA out of memory / Killed
```
**Solution:**
1. Reduce batch size to 1 (already default)
2. Enable 8-bit quantization (already enabled on GPU)
3. Use CPU instead of GPU
4. Increase RAM allocation

---

## 📚 Related Documentation

- **DEPLOY_NOW.md** - Step-by-step deployment guide
- **PRODUCTION_READY.md** - Verification summary
- **PRODUCTION_DEPLOYMENT.md** - Detailed technical guide
- **backend/API_CONNECTION_GUIDE.md** - API usage guide
- **backend/ARCHITECTURE.md** - System architecture

---

**Last Updated:** June 17, 2026  
**Status:** Production Ready ✅
