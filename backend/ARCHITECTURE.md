# Architecture Documentation

Detailed architecture and design decisions for the Decathlon Smart Search System with Fine-tuned Qwen 3:4B.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│               (Web Browser / API Client / Swagger UI)            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTP/REST
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   API LAYER (Flask + Swagger)                    │
│                      api_swagger.py                              │
│  ┌──────────────┬───────────────┬──────────────┐               │
│  │/parse-query  │/hybrid-search │/smart-search │               │
│  │(JSON only)   │(Products)     │(Complete)    │               │
│  └──────────────┴───────────────┴──────────────┘               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Function Calls
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MLX PLANNER LAYER                             │
│                     mlx_planner.py                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────┐         │
│  │         Smart Search Pipeline                      │         │
│  │                                                     │         │
│  │  1. Parse query with fine-tuned Qwen              │         │
│  │  2. Execute hybrid search                          │         │
│  │  3. Generate recommendations with Qwen            │         │
│  │  4. Return complete response                       │         │
│  └────────────────────────────────────────────────────┘         │
└─────┬──────────────────────┬──────────────────────┬────────────┘
      │                      │                      │
      │ MLX Inference        │ Search               │ Embeddings
      ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│  FINE-TUNED MLX  │  │  SEARCH PIPELINE │  │  EMBEDDING LAYER    │
│  mlx_planner.py  │  │search_pipeline.py│  │   embedding.py      │
│                  │  │                  │  │                     │
│ ┌──────────────┐ │  │ ┌──────────────┐ │  │ ┌─────────────────┐ │
│ │ Qwen 3:4B    │ │  │ │keyword_search│ │  │ │BAAI/bge-small   │ │
│ │ + LoRA       │ │  │ │semantic_rank │ │  │ │  (384 dims)     │ │
│ │ (MLX)        │ │  │ │hybrid_search │ │  │ │  Normalized     │ │
│ │              │ │  │ │search_task   │ │  │ └─────────────────┘ │
│ │ - Parse      │ │  │ └──────────────┘ │  │                     │
│ │ - Recommend  │ │  │                  │  │                     │
│ └──────────────┘ │  │                  │  │                     │
│ Model: 25MB      │  │                  │  │                     │
│ Location:        │  │                  │  │                     │
│ training/outputs/│  │                  │  │                     │
│ shopping_agent_  │  │                  │  │                     │
│ lora/            │  │                  │  │                     │
└──────┬───────────┘  └────────┬─────────┘  └──────────┬──────────┘
       │                       │                        │
       │ Pre-loaded on         │ SQL Queries            │
       │ API startup           │                        │
       │                       ▼                        │
       │            ┌──────────────────────┐            │
       │            │   DATABASE LAYER     │            │
       │            │       db.py          │            │
       │            │                      │            │
       │            │ ┌──────────────────┐ │            │
       │            │ │Connection Pooling│ │            │
       │            │ │   (psycopg2)     │ │            │
       │            │ └──────────────────┘ │            │
       │            └──────────┬───────────┘            │
       │                       │                        │
       │                       │ psycopg2               │
       │                       ▼                        │
       │            ┌──────────────────────┐            │
       │            │    PostgreSQL        │            │
       │            │    + pgvector        │            │
       │            │                      │            │
       │            │  ┌────────────────┐  │            │
       │            │  │   products     │  │            │
       │            │  │   (8,829 rows) │  │            │
       │            │  └────────────────┘  │            │
       │            │  ┌────────────────┐  │            │
       │            │  │product_embeddi-│  │◄───────────┘
       │            │  │ngs (vector384) │  │  Vector Similarity
       │            │  │  HNSW Index    │  │
       │            │  └────────────────┘  │
       │            └──────────────────────┘
       │
       │ No external Ollama needed!
       │ Model runs via Apple MLX
       └────────────────────────────────────
```

## Component Description

### 1. API Layer (`api_swagger.py`)
**Responsibility**: REST API interface with Swagger documentation

**Three Main Endpoints**:

1. **`POST /api/v1/shopping/parse-query`**
   - Input: Natural language query
   - Output: Structured JSON only
   - Purpose: Test model, custom integration
   - Speed: ~500ms

2. **`POST /api/v1/shopping/hybrid-search`**
   - Input: Structured JSON (from parse-query or manual)
   - Output: Products with similarity scores
   - Purpose: Fast search with pre-parsed query
   - Speed: ~100ms

3. **`POST /api/v1/shopping/smart-search`**
   - Input: Natural language query
   - Output: JSON + Products + Recommendations
   - Purpose: Complete AI shopping experience
   - Speed: ~1-2s

**Additional Endpoints**:
- `GET /api/v1/system/health` - Health check
- `GET /api/v1/products/categories` - List categories
- `POST /api/v1/products/compare` - Compare products

**Technologies**: Flask, Flask-RESTX, CORS

**Key Feature**: Model pre-loads on startup (no cold start)

### 2. MLX Planner Layer (`mlx_planner.py`)
**Responsibility**: Fine-tuned model integration and orchestration

**Key Functions**:

1. **`load_fine_tuned_model()`**
   - Loads Qwen 3:4B + LoRA adapter
   - Cached (loaded once)
   - Location: `training/outputs/shopping_agent_lora/`

2. **`parse_query_with_qwen(user_query)`**
   - Converts natural language → Structured JSON
   - Uses fine-tuned model
   - Returns: `{"intent": "search|task", "search_request": {...}}`

3. **`generate_recommendations(user_query, products)`**
   - Takes products from search
   - Generates natural language recommendations
   - Uses fine-tuned model

4. **`shopping_planner_mlx(user_query)`**
   - Complete pipeline: parse → search → recommend
   - Used by `/smart-search` endpoint

**Model Details**:
- Base: `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit`
- Technique: **QLoRA** (Quantized LoRA)
  - Base model: 4-bit quantized (1.5 GB)
  - Adapter: 16-bit LoRA (25 MB)
  - Rank: 16, Alpha: 32
- Training: 1,000 e-commerce examples
- Loss: 1.395 → 0.151 (89% improvement)
- Total Size: 1.5 GB (base) + 25 MB (adapter)

**Design Pattern**: Facade + Strategy

### 3. Search Pipeline Layer (`search_pipeline.py`)
**Responsibility**: Hybrid search execution

**Key Functions**:

1. **`keyword_search()`**
   - SQL filtering with ILIKE patterns
   - Filters: sport, category, price, keywords
   - Returns: 50-100 candidate products

2. **`semantic_rank()`**
   - pgvector similarity ranking
   - Input: query text + candidates
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

### 4. Embedding Layer (`embedding.py`)
**Responsibility**: Text-to-vector conversion

**Model**: BAAI/bge-small-en-v1.5
- Dimension: 384
- Normalized embeddings
- Singleton pattern (loaded once)

**Functions**:
- `get_embedding(text)` - Single text
- `get_embeddings_batch(texts)` - Batch processing

**Performance**: ~30-50ms per embedding

### 5. Database Layer (`db.py`)
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

### 6. Configuration (`config.py`)
**Responsibility**: Centralized configuration

**Settings**:
- Database credentials
- Model paths
- Search parameters
- System prompts

## Data Flow

### Smart Search Request Flow (Complete Pipeline)

```
1. User Query
   "Horse riding boots for kids below 3000"
   │
   ▼
2. API Layer (/smart-search)
   - Validate request
   - Extract query
   │
   ▼
3. MLX Planner - Parse Phase (~500ms)
   - load_fine_tuned_model() [cached]
   - parse_query_with_qwen(query)
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
4. Search Pipeline - Keyword Phase (~20ms)
   - keyword_search()
   - SQL: WHERE sport='Horse Riding' 
          AND price <= 3000
          AND (name LIKE '%boots%' OR name LIKE '%kids%')
   - Returns: 50-100 candidates
   │
   ▼
5. Embedding Generation (~50ms)
   - get_embedding("Riding Boots boots kids")
   - Returns: 384-dim vector
   │
   ▼
6. Database - Semantic Phase (~80ms)
   SELECT p.*, 
          1 - (pe.embedding <=> $1) AS similarity
   FROM products p
   JOIN product_embeddings pe ON p.product_id = pe.product_id
   WHERE p.product_id IN (candidates)
   ORDER BY pe.embedding <=> $1
   LIMIT 10
   │
   ▼
7. Search Results
   [10 products with similarity scores]
   │
   ▼
8. MLX Planner - Recommendation Phase (~500ms)
   - format_products_for_llm(products)
   - generate_recommendations()
   - Returns: Natural language recommendations
   │
   ▼
9. API Response
   {
     "status": "success",
     "user_query": "...",
     "parsed_query": {...},
     "products": [...],
     "recommendations": "I found some great options...",
     "metadata": {
       "model": "Qwen 3:4B Fine-tuned (MLX)",
       "products_found": 10
     }
   }
```

### Parse Query Request Flow (JSON Only)

```
1. User Query
   "Horse riding boots for kids below 3000"
   │
   ▼
2. API Layer (/parse-query)
   - Validate request
   │
   ▼
3. MLX Planner
   - parse_query_with_qwen(query)
   - Returns structured JSON
   │
   ▼
4. API Response
   {
     "status": "success",
     "parsed_query": {...},
     "intent": "search",
     "metadata": {"parse_time_ms": 485}
   }
   
   NO database access!
   NO search!
   ~500ms total
```

### Hybrid Search Request Flow (Products Only)

```
1. Structured JSON (from /parse-query or manual)
   {
     "intent": "search",
     "search_request": {...}
   }
   │
   ▼
2. API Layer (/hybrid-search)
   - Validate parsed_query
   │
   ▼
3. Search Pipeline
   - keyword_search() → candidates
   - semantic_rank() → top 10
   │
   ▼
4. API Response
   {
     "status": "success",
     "products": [...],
     "count": 10
   }
   
   NO LLM inference!
   ~100ms total
```

## Key Design Decisions

### 1. Fine-tuned Model vs. Generic LLM
**Previous**: Generic Qwen 3:4B via Ollama  
**Current**: Fine-tuned Qwen 3:4B + LoRA via MLX

**Rationale**:
- **Deterministic output**: Structured JSON, not conversational
- **Domain-specific**: Trained on 1,000 e-commerce queries
- **Faster**: No external Ollama server
- **Portable**: 25 MB adapter vs. several GB full model
- **Apple Silicon optimized**: MLX framework

### 2. Three Endpoint Design
**Rationale**:
- **Flexibility**: Choose speed vs. features
- **Testing**: Parse-query for model validation
- **Integration**: Hybrid-search for custom logic
- **User-facing**: Smart-search for complete experience

### 3. Model Pre-loading
**Rationale**:
- **No cold start**: Model loads on API startup
- **Fast responses**: First request is as fast as subsequent ones
- **Better UX**: Predictable latency

### 4. Hybrid Search (Two-Stage)
**Rationale**:
- **Stage 1 (Keyword)**: Fast SQL filtering (20ms)
- **Stage 2 (Semantic)**: Rank only candidates (80ms)
- **vs. Pure Semantic**: Would take 500ms for 8,829 products
- **5x faster** with same quality

### 5. Separate Parse + Search Endpoints
**Rationale**:
- **Debugging**: See what model understood
- **Custom logic**: Modify JSON before search
- **A/B testing**: Compare different models
- **Analytics**: Track query patterns

### 6. QLoRA (Quantized LoRA) vs. Full Fine-tune
**Rationale**:
- **QLoRA = LoRA + 4-bit Quantization**
- **Base Model**: 4-bit quantized (1.5 GB) vs. 16-bit (6 GB)
- **Adapter Size**: 25 MB vs. 3+ GB full fine-tuned model
- **Memory During Training**: 4x less than regular LoRA
- **Training Speed**: Faster with lower memory footprint
- **Flexibility**: Swap base model easily
- **Quality**: 89% loss reduction maintained
- **Training**: Faster, less GPU memory
- **Flexibility**: Swap base model easily
- **Quality**: 89% loss reduction maintained

## Performance Characteristics

### Model Inference (MLX)

**Query Parsing**:
- Time: ~500ms per query
- Model: Qwen 3:4B + LoRA (4-bit)
- Device: CPU (Apple Silicon)
- Memory: ~4GB

**Recommendation Generation**:
- Time: ~500ms per request
- Context: Products + user query
- Output: Natural language text

### Search Pipeline

**Keyword Search (SQL)**:
- Time: ~20ms
- Operation: ILIKE pattern matching
- Candidates: 50-100 products

**Semantic Ranking (pgvector)**:
- Time: ~80ms
- Operation: Vector similarity (HNSW)
- Results: Top 10 products
- Index: Approximate nearest neighbor

### Embedding Generation

**Single Query**:
- Model: BAAI/bge-small-en-v1.5
- Time: ~30-50ms (CPU)
- Dimension: 384

### End-to-End Latency

**Parse Query** (`/parse-query`):
```
Component           Time
───────────────────────
API overhead        5ms
MLX inference       500ms
───────────────────────
Total               ~500ms
```

**Hybrid Search** (`/hybrid-search`):
```
Component           Time
───────────────────────
API overhead        5ms
Keyword filter      20ms
Embedding gen       50ms
Semantic rank       80ms
───────────────────────
Total               ~150ms
```

**Smart Search** (`/smart-search`):
```
Component           Time
───────────────────────
API overhead        5ms
Parse (MLX)         500ms
Keyword filter      20ms
Embedding gen       50ms
Semantic rank       80ms
Recommend (MLX)     500ms
───────────────────────
Total               ~1.2s
```

## Scalability Considerations

### Horizontal Scaling

**Stateless Design**:
- Each request is independent
- Model loaded in each API instance
- Can add multiple API servers

**Components to Scale**:
1. API servers (4GB RAM each for model)
2. PostgreSQL (read replicas)
3. Load balancer (Nginx/HAProxy)

**Deployment**:
```
         ┌─────────────┐
         │Load Balancer│
         └──────┬──────┘
                │
        ┌───────┼───────┐
        ▼       ▼       ▼
    ┌─────┐ ┌─────┐ ┌─────┐
    │API 1│ │API 2│ │API 3│
    │+MLX │ │+MLX │ │+MLX │
    └──┬──┘ └──┬──┘ └──┬──┘
       └───────┼───────┘
               ▼
       ┌──────────────┐
       │ PostgreSQL   │
       │ (with replicas)
       └──────────────┘
```

### Vertical Scaling

**CPU-bound**:
- MLX inference (Apple Silicon recommended)
- Embedding generation
- More cores = better throughput

**Memory-bound**:
- MLX model: ~4GB
- Embedding model: ~1GB
- Connection pool: <100MB

**Requirements**:
- Minimum: 8GB RAM, 4 cores
- Recommended: 16GB RAM, 8 cores
- Optimal: Apple M1/M2/M3

### Caching Strategy

**Current**:
- Model: Singleton (loaded once per API instance)
- Database: Connection pooling
- Embeddings: In database

**Future** (with Redis):
- Query embeddings (common queries)
- Parsed queries (frequent patterns)
- Search results (popular queries)
- TTL: 1 hour for query cache

## Security Considerations

### SQL Injection Protection
- Parameterized queries throughout
- No string concatenation
- psycopg2 built-in protection

### Input Validation
- Query length limits (max 500 chars)
- JSON schema validation
- Type checking in API layer

### Model Security
- Local model (no external API)
- No user data sent externally
- Model weights read-only

### Authentication (Production)
- Add JWT tokens
- API keys for services
- Rate limiting per user

### CORS
- Configured for development
- Production: Restrict origins

### Environment Secrets
- Database credentials in .env
- Never commit .env
- Use AWS Secrets Manager in production

## Monitoring and Observability

### Key Metrics

**API Layer**:
- Request rate (req/s)
- Response latency (p50, p95, p99)
- Error rate (5xx, 4xx)
- Endpoint usage distribution

**Model Layer**:
- Inference latency (parse, recommend)
- Model load time (startup)
- Memory usage
- Parse success rate

**Search Layer**:
- Keyword candidates count
- Semantic ranking latency
- Products found distribution
- Search cache hit rate

**Database**:
- Query latency
- Connection pool usage
- Index hit rate
- Slow query log

### Logging

```python
INFO  - User query received
INFO  - Parsed query: {"intent": "search", ...}
INFO  - Keyword search: 87 candidates
INFO  - Semantic ranking: top 10 selected
INFO  - Recommendations generated
INFO  - Response sent (total: 1234ms)
```

### Recommended Tools

- **APM**: New Relic, DataDog
- **Logs**: ELK Stack, Loki
- **Metrics**: Prometheus + Grafana
- **Tracing**: Jaeger (distributed tracing)

## Error Handling Strategy

### Graceful Degradation

1. **Model Load Failure**: 
   - API returns 503
   - Log error with details
   - Instruction: Train model first

2. **Database Unavailable**:
   - Return cached results
   - Fallback to empty response
   - Retry with backoff

3. **Parse Failure**:
   - Return error to user
   - Log invalid query
   - Suggest query format

### Retry Logic

- Database: 3 retries, exponential backoff
- Model inference: 2 retries, timeout
- Embedding: Fast failure (no retry)

### User-Facing Errors

```python
{
  "status": "error",
  "error": "Model not found",
  "message": "Please train the model first: cd training && python3 train_mlx.py"
}
```

## Testing Strategy

### Unit Tests
- Search functions (keyword, semantic, hybrid)
- Model loading and inference
- Database queries
- Decimal conversion
- JSON parsing

### Integration Tests
- API endpoints (parse, search, smart)
- Model + search pipeline
- Database + embeddings
- Error scenarios

### Performance Tests
- Latency benchmarks
- Concurrent requests
- Memory usage
- Model load time

### Test Scripts
- `test_smart_search_fixed.py` - All endpoints
- `test_parse_query.py` - Parse endpoint
- `inference_mlx.py` - Model standalone

## Model Training

### Training Data
- Location: `training/data/train_mlx.jsonl`
- Format: Chat-ML (MLX format)
- Examples: 1,000 queries
- Quality: Hand-crafted + validated

### Training Process
```bash
cd training
python3 train_mlx.py
```

**Configuration**:
- LoRA rank: 16
- LoRA alpha: 32
- Batch size: 4
- Learning rate: 1e-4
- Epochs: 3
- Time: ~30-45 minutes

**Results**:
- Initial loss: 1.395
- Final loss: 0.151
- Improvement: 89%

### Model Location
```
training/outputs/shopping_agent_lora/
├── adapters.safetensors    # Main adapter (25MB)
├── adapter_config.json      # Configuration
└── 0000XXX_*.safetensors   # Checkpoints
```

## Comparison: Old vs. New Architecture

### Old Architecture (Ollama)
```
User → API → Planner → Ollama (external) → Qwen 3:4B (generic)
                ↓
           Python Tools
                ↓
           PostgreSQL
```

**Characteristics**:
- Generic Qwen 3:4B via Ollama
- Conversational responses
- ~6-7 seconds per request
- External Ollama server required
- Iterative planning (3 iterations)
- Large model download (several GB)

### New Architecture (MLX + Fine-tuned)
```
User → API → MLX Planner → Fine-tuned Qwen (local)
                ↓
           Search Pipeline
                ↓
           PostgreSQL
```

**Characteristics**:
- Fine-tuned Qwen 3:4B via MLX
- Structured JSON output
- ~1-2 seconds per request
- No external server needed
- Single-pass execution
- Small adapter (25 MB)

### Benefits of New Architecture

1. **Faster**: 1-2s vs 6-7s
2. **Deterministic**: JSON vs. conversational
3. **Portable**: 25MB vs several GB
4. **Flexible**: 3 endpoints vs. 1
5. **Testable**: Parse separately
6. **Optimized**: Apple Silicon MLX
7. **Custom**: Domain-specific fine-tuning

## Dependencies

### Python Libraries
```
# Core
psycopg2-binary    # PostgreSQL
sentence-transformers  # Embeddings
mlx-lm             # Apple MLX for model
flask              # Web framework
flask-restx        # Swagger
flask-cors         # CORS
python-dotenv      # Config

# Training
datasets           # Data handling
transformers       # Model training
```

### External Services
- **PostgreSQL 14+**: Database
- **pgvector**: Vector extension
- **Apple Silicon**: For MLX (M1/M2/M3)

### System Requirements
- Python 3.11+
- macOS (for MLX)
- 8GB+ RAM (16GB recommended)
- 50GB disk space

## Maintenance

### Regular Tasks
- Database vacuum (weekly)
- Model retraining (monthly with new data)
- Log rotation (daily)
- Backup verification (weekly)
- Dependency updates (monthly)

### Health Checks
- API: GET `/api/v1/system/health`
- Database: Connection test
- Model: Load test
- Disk space: Monitor

### Model Updates

**When to retrain**:
- New product categories
- Query pattern changes
- User feedback indicates errors
- Monthly retraining schedule

**How to retrain**:
```bash
cd training
# Update data/train_mlx.jsonl
python3 train_mlx.py
# Test: python3 inference_mlx.py
# Deploy: Restart API
```

## References

- [MLX Documentation](https://ml-explore.github.io/mlx/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [HNSW Algorithm](https://arxiv.org/abs/1603.09320)
- [BAAI/bge Models](https://huggingface.co/BAAI/bge-small-en-v1.5)
- [LoRA Paper](https://arxiv.org/abs/2106.09685)
- [Qwen Models](https://huggingface.co/Qwen)

---

**Architecture Status**: Production-ready with fine-tuned model  
**Last Updated**: June 16, 2026  
**Version**: 2.0 (MLX + Fine-tuned)
