# Architecture Documentation

Detailed architecture and design decisions for the Decathlon Smart Search System with Fine-tuned Qwen2.5-1.5B-Instruct.

## System Architecture (Split Architecture - Render + Mac)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│               (Web Browser / API Client / Swagger UI)            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTP/REST
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              API LAYER (Flask + Swagger) - RENDER                │
│                   Thin API Gateway (512 MB RAM)                  │
│                      api_swagger.py                              │
│  ┌──────────────┬───────────────┬──────────────┐               │
│  │/parse-query  │/hybrid-search │/smart-search │               │
│  │(JSON only)   │(Products)     │(Complete)    │               │
│  └──────────────┴───────────────┴──────────────┘               │
│                                                                  │
│  Memory Usage: ~200 MB                                          │
│  • PostgreSQL client: 50 MB                                     │
│  • Flask + deps: 100 MB                                         │
│  • NO torch: 0 MB ✓                                             │
│  • NO models: 0 MB ✓                                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTP via ngrok
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│           LOCAL MODEL SERVER - MAC (Apple Silicon)               │
│                   All ML Models (Port 8001)                      │
│                  local_model_server.py                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Qwen2.5-1.5B-Instruct + LoRA (~1,500 MB)          │        │
│  │  • Model: Qwen/Qwen2.5-1.5B-Instruct               │        │
│  │  • Adapter: training/outputs/qwen25_1_5b_lora_hf/  │        │
│  │  • Device: MPS (Apple Silicon GPU)                  │        │
│  │  • Endpoints: /parse-query, /generate              │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  SentenceTransformer (~300 MB)                      │        │
│  │  • Model: all-MiniLM-L6-v2                          │        │
│  │  • Dimension: 384                                    │        │
│  │  • Endpoint: /embed                                  │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  Total Memory: ~1,900 MB                                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Results
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PLANNER LAYER - RENDER                        │
│                     hf_planner.py                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────┐         │
│  │         Smart Search Pipeline                      │         │
│  │                                                     │         │
│  │  1. Parse query with Qwen (via HTTP)              │         │
│  │  2. Execute hybrid search (local)                  │         │
│  │  3. Generate recommendations with Qwen (via HTTP)  │         │
│  │  4. Return complete response                       │         │
│  └────────────────────────────────────────────────────┘         │
│                                                                  │
│  local_model_client.py - HTTP client for Mac server             │
└─────┬──────────────────────┬──────────────────────┬────────────┘
      │                      │                      │
      │ HTTP Client          │ Search               │ HTTP Client
      ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│  LOCAL MODEL     │  │  SEARCH PIPELINE │  │  LOCAL MODEL        │
│  CLIENT (HTTP)   │  │search_pipeline.py│  │  CLIENT (HTTP)      │
│                  │  │                  │  │                     │
│ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌─────────────────┐ │
│ │parse_query() │ │  │ │keyword_search│ │  │ │embed()          │ │
│ │generate()    │ │  │ │semantic_rank │ │  │ │                 │ │
│ │              │ │  │ │hybrid_search │ │  │ │  Calls:         │ │
│ │Calls:        │ │  │ │search_task   │ │  │ │  POST /embed    │ │
│ │POST /parse-  │ │  │ └──────────────┘ │  │ └─────────────────┘ │
│ │  query       │ │  │                  │  │                     │
│ │POST /generate│ │  │                  │  │                     │
│ └──────────────┘ │  │                  │  │                     │
│                  │  │                  │  │                     │
│ NO local models  │  │                  │  │ NO local models     │
│ HTTP only        │  │                  │  │ HTTP only           │
└──────────────────┘  └────────┬─────────┘  └─────────────────────┘
                               │
                               │ SQL Queries
                               ▼
                    ┌──────────────────────┐
                    │   DATABASE LAYER     │
                    │       db.py          │
                    │                      │
                    │ ┌──────────────────┐ │
                    │ │Connection Pooling│ │
                    │ │   (psycopg2)     │ │
                    │ └──────────────────┘ │
                    └──────────┬───────────┘
                               │
                               │ psycopg2
                               ▼
                    ┌──────────────────────┐
                    │    PostgreSQL        │
                    │    + pgvector        │
                    │                      │
                    │  ┌────────────────┐  │
                    │  │   products     │  │
                    │  │   (8,829 rows) │  │
                    │  └────────────────┘  │
                    │  ┌────────────────┐  │
                    │  │product_embeddi-│  │
                    │  │ngs (vector384) │  │
                    │  │  HNSW Index    │  │
                    │  └────────────────┘  │
                    └──────────────────────┘
```

## Component Description

### 1. API Layer (`api_swagger.py`) - RENDER
**Responsibility**: REST API interface with Swagger documentation  
**Location**: Render free tier (512 MB RAM)  
**Memory**: ~200 MB

**Three Main Endpoints**:

1. **`POST /api/v1/shopping/parse-query`**
   - Input: Natural language query
   - Output: Structured JSON only
   - Purpose: Test model, custom integration
   - Speed: ~1-2s (HTTP to Mac)

2. **`POST /api/v1/shopping/hybrid-search`**
   - Input: Structured JSON (from parse-query or manual)
   - Output: Products with similarity scores
   - Purpose: Fast search with pre-parsed query
   - Speed: ~300ms (includes embedding via HTTP)

3. **`POST /api/v1/shopping/smart-search`**
   - Input: Natural language query
   - Output: JSON + Products + Recommendations
   - Purpose: Complete AI shopping experience
   - Speed: ~2-4s (includes 2 HTTP calls to Mac)

**Additional Endpoints**:
- `GET /api/v1/system/health` - Health check
- `GET /api/v1/products/categories` - List categories
- `POST /api/v1/products/compare` - Compare products

**Technologies**: Flask, Flask-RESTX, CORS

**Key Feature**: NO model loading - thin API gateway

---

### 2. Local Model Server (`local_model_server.py`) - MAC
**Responsibility**: All ML model inference  
**Location**: Mac with Apple Silicon (M1/M2/M3/M4/M5)  
**Memory**: ~1,900 MB

**Endpoints**:

1. **`POST /parse-query`**
   - Input: `{"query": "running shoes under 5000"}`
   - Output: `{"intent": "search", "search_request": {...}}`
   - Model: Qwen2.5-1.5B-Instruct + LoRA
   - Device: MPS (Apple Silicon)
   - Time: ~1-2s

2. **`POST /generate`**
   - Input: `{"prompt": "...", "max_new_tokens": 512}`
   - Output: `{"response": "..."}`
   - Model: Qwen2.5-1.5B-Instruct + LoRA
   - Time: ~1-2s

3. **`POST /embed`**
   - Input: `{"texts": ["text1", "text2"]}`
   - Output: `{"embeddings": [[...], [...]], "dimension": 384}`
   - Model: sentence-transformers/all-MiniLM-L6-v2
   - Time: ~50-100ms

4. **`GET /health`**
   - Health check endpoint
   - Returns model status

**Model Details**:
- **LLM**: Qwen/Qwen2.5-1.5B-Instruct
  - Base model: ~1,500 MB (FP16)
  - LoRA adapter: ~35 MB
  - Location: `training/outputs/qwen25_1_5b_lora_hf/`
  - Device: MPS (Apple Silicon GPU)
  - Format: ChatML (no system prompts)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2
  - Size: ~300 MB
  - Dimension: 384
  - Normalized embeddings

**Technologies**: FastAPI, PyTorch, Transformers, PEFT, sentence-transformers

---

### 3. Local Model Client (`local_model_client.py`) - RENDER
**Responsibility**: HTTP client for calling Mac server  
**Location**: Render backend

**Key Functions**:

1. **`get_client()`**
   - Returns singleton client instance
   - Configured with `LOCAL_MODEL_URL` (ngrok URL)
   - Timeout: 120s

2. **`client.parse_query(query)`**
   - Calls `POST /parse-query` on Mac server
   - Returns: `{"intent": "...", "search_request": {...}}`

3. **`client.generate(prompt, max_new_tokens)`**
   - Calls `POST /generate` on Mac server
   - Returns: Generated text string

4. **`client.embed(texts)`**
   - Calls `POST /embed` on Mac server
   - Returns: List of embedding vectors

5. **`client.health_check()`**
   - Calls `GET /health`
   - Returns: Server health status

**Configuration**:
- `LOCAL_MODEL_URL`: ngrok URL (e.g., `https://xxxx.ngrok-free.app`)
- `MODEL_REQUEST_TIMEOUT`: 120 seconds

**Error Handling**:
- Connection errors
- Timeouts
- HTTP errors
- Invalid responses

---

### 4. Planner Layer (`hf_planner.py`) - RENDER
**Responsibility**: Orchestration and deduplication

**Key Functions**:

1. **`deduplicate_search_requests(search_requests)`**
   - Removes duplicate (sport, category) pairs
   - Applied at parsing and search stages
   - Logs warnings when duplicates removed

2. **`parse_query_with_local_model(user_query)`**
   - Calls local model client
   - Returns structured JSON
   - Includes deduplication

3. **`execute_search(parsed_query)`**
   - Keyword search → candidates
   - Semantic ranking → top 10
   - Deduplicates task search_requests

4. **`generate_recommendations(user_query, products)`**
   - Calls local model for natural language
   - Uses product context

5. **`shopping_planner_hf(user_query)`**
   - Complete pipeline: parse → search → recommend
   - Extensive DEBUG logging
   - Used by `/smart-search` endpoint

**Design Pattern**: Orchestrator + HTTP Client

---

### 5. Search Pipeline Layer (`search_pipeline.py`) - RENDER
**Responsibility**: Hybrid search execution

**Key Functions**:

1. **`keyword_search()`**
   - SQL filtering with ILIKE patterns
   - Filters: sport, category, price, keywords
   - Returns: 50-100 candidate products

2. **`semantic_rank()`**
   - pgvector similarity ranking
   - Input: query text + candidates
   - Uses remote embedding via HTTP
   - Returns: Top 10 products with scores

3. **`hybrid_search()`**
   - Combines keyword + semantic
   - Flow: Filter → Rank → Return
   - Fallback: sport-wide search if no candidates

4. **`search_task()`**
   - Multi-category search (task intent)
   - Example: "camping" → tent + sleeping bag
   - Returns: dict of products by category

5. **`format_products_for_llm()`**
   - Formats products for Qwen consumption
   - Used in recommendation generation

**Search Strategy**: Two-stage hybrid approach

---

### 6. Embedding Layer (`embedding.py`) - RENDER
**Responsibility**: Remote embedding via HTTP  
**NO local model loading**

**Functions**:
- `get_embedding(text)` - Single text via HTTP
- `get_embeddings_batch(texts)` - Batch via HTTP

**Implementation**:
```python
from local_model_client import get_client

def get_embedding(text):
    client = get_client()
    embeddings = client.embed([text])
    return embeddings[0]
```

**Performance**: ~100ms per request (HTTP + inference)

---

### 7. Database Layer (`db.py`) - RENDER
**Responsibility**: PostgreSQL connection management

**Features**:
- Connection pooling (SimpleConnectionPool)
- RealDictCursor for dict results
- Decimal to float conversion (JSON serialization)
- Transaction management
- Error handling and logging

**Pool Configuration**:
- Min connections: 2
- Max connections: 20

**Key Functions**:
- `initialize_pool()` - Setup connections
- `connect_db()` - Get connection from pool
- `release_connection()` - Return to pool
- `close_pool()` - Cleanup

---

### 8. Configuration (`config.py`)
**Responsibility**: Centralized configuration

**Settings**:
- Database credentials
- Model paths
- Search parameters
- System prompts

---

## Data Flow

### Smart Search Request Flow (Complete Pipeline)

```
1. User Query
   "Horse riding boots for kids below 3000"
   │
   ▼
2. API Layer (/smart-search) - RENDER
   - Validate request
   - Extract query
   │
   ▼
3. HTTP → Mac Server (/parse-query) (~1-2s)
   - Qwen2.5-1.5B + LoRA inference
   - ChatML format
   - Returns: {
       "intent": "search",
       "search_request": {
         "sport": "Horse Riding",
         "category": "Riding Boots",
         "keywords": ["boots", "kids"],
         "price_limit": 3000
       }
     }
   │
   ▼
4. Deduplication Check - RENDER
   - Remove duplicate search_requests if present
   - Log warnings
   │
   ▼
5. Search Pipeline - Keyword Phase (~20ms)
   - keyword_search()
   - SQL: WHERE sport='Horse Riding' 
          AND price <= 3000
          AND (name LIKE '%boots%' OR name LIKE '%kids%')
   - Returns: 50-100 candidates
   │
   ▼
6. HTTP → Mac Server (/embed) (~100ms)
   - sentence-transformers/all-MiniLM-L6-v2
   - Input: "Riding Boots boots kids"
   - Returns: 384-dim vector
   │
   ▼
7. Database - Semantic Phase (~80ms)
   SELECT p.*, 
          1 - (pe.embedding <=> $1) AS similarity
   FROM products p
   JOIN product_embeddings pe ON p.product_id = pe.product_id
   WHERE p.product_id IN (candidates)
   ORDER BY pe.embedding <=> $1
   LIMIT 10
   │
   ▼
8. Search Results
   [10 products with similarity scores]
   │
   ▼
9. HTTP → Mac Server (/generate) (~1-2s)
   - format_products_for_llm(products)
   - Qwen2.5-1.5B + LoRA inference
   - Returns: Natural language recommendations
   │
   ▼
10. API Response
    {
      "status": "success",
      "user_query": "...",
      "parsed_query": {...},
      "products": [...],
      "recommendations": "I found some great options...",
      "metadata": {
        "model": "Qwen2.5-1.5B-Instruct (Local Server)",
        "products_found": 10
      }
    }
```

---

## Key Design Decisions

### 1. Split Architecture (Render + Mac)
**Rationale**:
- **Render Free Tier**: 512 MB RAM insufficient for ML models
- **Mac Server**: Handles all ML inference (~1,900 MB)
- **Render Backend**: Thin API gateway (~200 MB)
- **Communication**: HTTP via ngrok tunnel
- **Cost**: Free tier deployment viable

### 2. All ML Models on Mac
**Components on Mac**:
- Qwen2.5-1.5B-Instruct + LoRA (~1,500 MB)
- SentenceTransformer (~300 MB)

**Components on Render**:
- PostgreSQL client (~50 MB)
- Flask + dependencies (~100 MB)
- HTTP client (minimal)

**Benefits**:
- Render fits in 512 MB free tier
- Mac has sufficient RAM
- Apple Silicon GPU acceleration (MPS)

### 3. ChatML Format (No System Prompts)
**Rationale**:
- Training data uses ChatML format
- `apply_chat_template()` adds unwanted system prompts
- Manual format matches training exactly
- Produces clean JSON output

### 4. Deduplication at Multiple Stages
**Rationale**:
- Model can generate duplicate search_requests
- Applied after parsing (clean model output)
- Applied before search (prevent duplicate queries)
- Defensive programming

### 5. Three Endpoint Design
**Rationale**:
- **Flexibility**: Choose speed vs. features
- **Testing**: Parse-query for model validation
- **Integration**: Hybrid-search for custom logic
- **User-facing**: Smart-search for complete experience

### 6. Hybrid Search (Two-Stage)
**Rationale**:
- **Stage 1 (Keyword)**: Fast SQL filtering (20ms)
- **Stage 2 (Semantic)**: Rank only candidates (80ms + HTTP)
- **vs. Pure Semantic**: Would require embedding 8,829 products
- **Faster** with same quality

### 7. ngrok for Local Server Exposure
**Rationale**:
- Easy local → internet tunnel
- HTTPS support
- Free tier available
- Alternative to cloud GPU instances

---

## Performance Characteristics

### Model Inference (Mac - MPS)

**Query Parsing**:
- Time: ~1-2s per query
- Model: Qwen2.5-1.5B + LoRA (FP16)
- Device: MPS (Apple Silicon)
- Memory: ~1,500 MB

**Recommendation Generation**:
- Time: ~1-2s per request
- Context: Products + user query
- Output: Natural language text

**Embeddings**:
- Time: ~50-100ms per batch
- Model: all-MiniLM-L6-v2
- Dimension: 384

### Search Pipeline (Render)

**Keyword Search (SQL)**:
- Time: ~20ms
- Operation: ILIKE pattern matching
- Candidates: 50-100 products

**Semantic Ranking (pgvector)**:
- Time: ~80ms (SQL only)
- Operation: Vector similarity (HNSW)
- Results: Top 10 products
- Index: Approximate nearest neighbor

### HTTP Overhead

**Render → Mac (via ngrok)**:
- Latency: ~50-200ms per request
- Depends on network conditions
- ngrok free tier: 40 requests/minute limit

### End-to-End Latency

**Parse Query** (`/parse-query`):
```
Component           Time
───────────────────────
API overhead        5ms
HTTP to Mac         100ms
Model inference     1-2s
HTTP response       50ms
───────────────────────
Total               ~1.2-2.2s
```

**Hybrid Search** (`/hybrid-search`):
```
Component           Time
───────────────────────
API overhead        5ms
Keyword filter      20ms
HTTP to Mac (embed) 150ms
Semantic rank       80ms
───────────────────────
Total               ~250ms
```

**Smart Search** (`/smart-search`):
```
Component           Time
───────────────────────
API overhead        5ms
HTTP (parse)        1.2s
Keyword filter      20ms
HTTP (embed)        150ms
Semantic rank       80ms
HTTP (recommend)    1.2s
Deduplication       1ms
───────────────────────
Total               ~2.7s
```

---

## Scalability Considerations

### Current Limitations

**ngrok Free Tier**:
- 40 requests/minute limit
- Tunnel expires after 8 hours
- Single connection

**Mac Server**:
- Single instance
- No load balancing
- Requires Mac to be on

**Render Free Tier**:
- 512 MB RAM
- Spins down after inactivity

### Production Recommendations

**For Mac Server**:
1. Replace ngrok with cloud server
2. Deploy to AWS/GCP with GPU
3. Add load balancer for multiple instances
4. Use Redis for caching

**For Render Backend**:
1. Upgrade to paid tier (more RAM)
2. Add Redis for caching
3. Connection pooling already in place

**Alternative**: Deploy both on same cloud instance (AWS, GCP, Azure)

---

## Deployment

### Local Development

**Terminal 1 - Mac Server**:
```bash
python3 local_model_server.py
```

**Terminal 2 - ngrok**:
```bash
ngrok http 8001
```

**Terminal 3 - Render Backend (local)**:
```bash
cd backend
export LOCAL_MODEL_URL=http://localhost:8001
python3 api_swagger.py
```

### Production Deployment

**Mac Server**:
```bash
python3 local_model_server.py
ngrok http 8001
```

**Render**:
1. Set environment variable: `LOCAL_MODEL_URL=https://xxxx.ngrok-free.app`
2. Push to git: `git push origin main`
3. Render auto-deploys

---

## Memory Breakdown

### Render Backend (512 MB Limit)
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

## Error Handling Strategy

### Graceful Degradation

1. **Local Server Unavailable**: 
   - Return 503 Service Unavailable
   - Log connection error
   - Message: "Model server not reachable"

2. **Database Unavailable**:
   - Return cached results if available
   - Retry with backoff
   - Clear error message

3. **Parse Failure**:
   - Return error to user
   - Log invalid query
   - Suggest query format

### Retry Logic

- HTTP to Mac: 2 retries, timeout 120s
- Database: 3 retries, exponential backoff
- Fast failure for embeddings

---

## Testing

### Test Scripts

- `test_local_model.py` - Test Mac server endpoints
- `test_embeddings.py` - Test embedding endpoint
- `test_chatml_inference.py` - Test ChatML format
- `test_both_intents.py` - Test search and task intents
- `test_duplicates.py` - Test deduplication

### Running Tests

```bash
# Terminal 1: Start Mac server
python3 local_model_server.py

# Terminal 2: Run tests
python3 test_local_model.py
python3 test_embeddings.py
python3 test_duplicates.py
```

---

## Model Training

### Training Data
- Location: `training/data/train.jsonl`
- Format: ChatML
- Examples: 250+ queries
- Quality: Hand-crafted + validated

### Training Process
```bash
cd training
python3 train_hf.py
```

**Configuration**:
- Base: Qwen/Qwen2.5-1.5B-Instruct
- LoRA rank: 16
- LoRA alpha: 32
- Batch size: 4
- Learning rate: 1e-4
- Epochs: 3
- Device: MPS (Apple Silicon)

### Model Location
```
training/outputs/qwen25_1_5b_lora_hf/
├── adapter_model.safetensors  # Adapter (35MB)
├── adapter_config.json         # Configuration
└── tokenizer.json              # Tokenizer
```

---

## Dependencies

### Render Backend (`requirements_render.txt`)
```
# NO torch
# NO transformers
# NO sentence-transformers

flask
requests
psycopg2-binary
numpy<2.0  # Minimal, for arrays only
pgvector
```

### Mac Server (`requirements_local_server.txt`)
```
torch>=2.0.0
transformers>=4.36.0
peft>=0.7.0
sentence-transformers>=2.2.0
fastapi>=0.104.0
uvicorn>=0.24.0
numpy<2.0.0  # Important for compatibility
```

---

## Comparison: Render Only vs. Split Architecture

### Render Only (Failed)
```
Render (512 MB)
├─ SentenceTransformer (300 MB)
├─ Qwen Model (1,500 MB) ← DOESN'T FIT!
└─ PostgreSQL client (50 MB)

Result: Out of Memory
```

### Split Architecture (Success)
```
Render (512 MB)
├─ HTTP Client (minimal)
├─ PostgreSQL client (50 MB)
└─ Flask + deps (100 MB)
✓ Total: ~200 MB

Mac
├─ Qwen2.5-1.5B + LoRA (1,500 MB)
└─ SentenceTransformer (300 MB)
✓ Total: ~1,900 MB
```

---

## References

- [Qwen2.5 Models](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- [PEFT/LoRA](https://github.com/huggingface/peft)
- [sentence-transformers](https://www.sbert.net/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [FastAPI](https://fastapi.tiangolo.com/)
- [ngrok](https://ngrok.com/)

---

**Architecture Status**: Production (Split Architecture)  
**Last Updated**: June 19, 2026  
**Version**: 3.0 (Render + Mac Local Server)  
**Deployment**: Render Free Tier (512 MB) + Mac with Apple Silicon
