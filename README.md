# Decathlon Smart Shopping API

Single unified API with Qwen3-4B intent parser for natural language shopping queries.

## Architecture

```
User → api_swagger.py (port 5000)
         ↓
      local_model_server.py (port 8000)
         ↓
      Qwen3-4B + LoRA → Intent JSON
         ↓
      Tools (Search, Task, Compare, Alternatives)
         ↓
      PostgreSQL + pgvector
         ↓
      Results
```

## Quick Start

### 1. Train the Model (One-Time Setup)

```bash
cd training
./setup_mlx.sh              # Install MLX and dependencies
source venv_mlx/bin/activate
python3 train_mlx.py --mode train --iters 300
```

Expected time: ~15 minutes on M1/M2/M3 Mac

### 2. Start the System

```bash
./start_system.sh
```

This starts:
1. **Local Model Server** (port 8000) - Qwen3-4B intent parser
2. **Backend API** (port 5000) - Swagger-documented REST API

### 3. Test the API

```bash
curl -X POST http://localhost:5000/api/v1/query \
  -H "Api-Key: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -H "Content-Type: application/json" \
  -d '{"query":"running shoes under 5000"}'
```

Or visit the Swagger UI:
```
http://localhost:5000/docs
```

## Supported Queries

### Search Intent
```
"running shoes under 5000"
"waterproof hiking shoes"
"football boots for men"
```

### Task Intent (Activity Shopping)
```
"I want to start playing golf"
"golf equipment under 15000"
"camping gear for beginners"
```

### Compare Intent
```
"compare MH500 and NH500"
"compare product ABC123 with XYZ456"
```

### Alternatives Intent
```
"alternatives to MH500"
"similar products to ABC123"
```

## API Endpoints

### POST /api/v1/query
Execute natural language query

**Request:**
```json
{
  "query": "running shoes under 5000"
}
```

**Response:**
```json
{
  "type": "search",
  "products": [...],
  "total": 10,
  "query": "running shoes under 5000"
}
```

### GET /api/v1/system/health
Check system health

**Response:**
```json
{
  "status": "healthy",
  "api": "running",
  "model_server": "connected",
  "database": "connected",
  "model": "mlx-community/Qwen3-4B-Instruct-2507-4bit"
}
```

### GET /docs
Swagger UI documentation

## Development

### Run Model Server Only
```bash
cd training
source venv_mlx/bin/activate
python3 local_model_server.py
```

### Run Backend API Only
```bash
cd backend
python3 api_swagger.py
```

### Test Individual Tools
```bash
cd backend
python3 test_agent_api.py
```

## Project Structure

```
backend/
├── api_swagger.py          # Single public API (Flask + Flask-RESTX)
├── tools/
│   ├── search_tool.py      # Product search with filters
│   ├── task_tool.py        # Activity-based shopping
│   ├── compare_tool.py     # Product comparison
│   └── alternatives_tool.py # Find similar products
├── services/
│   ├── hybrid_search.py    # Hybrid search (SQL + pgvector)
│   └── embedding_service.py # Semantic embeddings
├── models/
│   └── schemas.py          # Pydantic validation schemas
├── database.py             # PostgreSQL connection pool
└── db/
    └── queries.py          # Database queries

training/
├── local_model_server.py   # FastAPI intent parser
├── train_mlx.py            # MLX training script
├── data/
│   ├── train.jsonl         # Training data (3166 examples)
│   ├── valid.jsonl
│   └── test.jsonl
└── outputs/
    └── qwen3_4b_lora_mlx/  # Fine-tuned adapter weights
```

## Training Data Format (ChatML)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a Decathlon shopping assistant..."
    },
    {
      "role": "user",
      "content": "running shoes under 5000"
    },
    {
      "role": "assistant",
      "content": "{\"intent\":\"search\",\"search_request\":{\"sport\":\"Running\",\"category_level_1\":\"Footwear\",\"keywords\":[\"running\",\"shoes\"],\"price_limit\":5000}}"
    }
  ]
}
```

## Environment Variables

```bash
# Backend
API_KEY=decathlon_smart_search_2024_secure_key_abc123xyz
LOCAL_MODEL_URL=http://localhost:8000

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=decathlon_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Model Server
MODEL_SERVER_PORT=8000
```

## Tech Stack

- **Backend**: Flask + Flask-RESTX
- **Model**: Qwen3-4B-Instruct-4bit + LoRA fine-tuning
- **ML Framework**: MLX (Apple Silicon optimization)
- **Database**: PostgreSQL + pgvector
- **Validation**: Pydantic
- **Python**: 3.11

## Deployment

### Render (Backend Only)
- Build: `pip install -r requirements_render.txt`
- Start: `gunicorn api_swagger:app --bind 0.0.0.0:$PORT`
- RAM: ~200 MB (fits in 512 MB free tier)
- **Note**: Model server must run on separate Mac machine with ngrok

### Local Mac (Full System)
- Supports Apple Silicon (M1/M2/M3)
- RAM: ~2 GB (model) + ~200 MB (backend)
- Use `./start_system.sh` to run both services

## Testing

```bash
# Test search
curl -X POST http://localhost:5000/api/v1/query \
  -H "Api-Key: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -H "Content-Type: application/json" \
  -d '{"query":"running shoes under 5000"}'

# Test task
curl -X POST http://localhost:5000/api/v1/query \
  -H "Api-Key: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -H "Content-Type: application/json" \
  -d '{"query":"I want to start playing golf with budget 15000"}'

# Test health
curl http://localhost:5000/api/v1/system/health
```

## Troubleshooting

### Model server not connecting
```bash
# Check if model server is running
curl http://localhost:8000/health

# If not, start it manually
cd training
source venv_mlx/bin/activate
python3 local_model_server.py
```

### Database connection failed
```bash
# Check PostgreSQL is running
psql -h localhost -U postgres -d decathlon_rag -c "SELECT 1"

# Check environment variables
cat backend/.env
```

### MLX not installed
```bash
cd training
./setup_mlx.sh
source venv_mlx/bin/activate
python3 -c "import mlx_lm; print('MLX installed')"
```
