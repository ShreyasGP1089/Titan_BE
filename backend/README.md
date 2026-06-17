# Decathlon Conversational Shopping Assistant

An intelligent shopping engine for conversational commerce using Qwen 3:4B, PostgreSQL with pgvector, and semantic search.

## Architecture

```
User
  ↓
Qwen 3:4B (via Ollama)
  ↓
Python Tools
  ├── hybrid_search()
  ├── compare_products()
  └── get_categories()
  ↓
PostgreSQL + pgvector
  ├── products (metadata)
  └── product_embeddings (vector(384))
  ↓
Qwen 3:4B (reasoning)
  ↓
User Response
```

## Key Features

- **Semantic Search**: Uses BAAI/bge-small-en-v1.5 embeddings with pgvector HNSW index
- **Hybrid Filtering**: Combines vector similarity with SQL filters (sport, price, rating)
- **Iterative Planning**: Qwen performs multi-step reasoning with up to 3 tool iterations
- **Modular Design**: Separation of concerns (DB, embeddings, tools, LLM, planning)
- **Connection Pooling**: Efficient database resource management
- **Production-Ready**: Comprehensive logging, error handling, and configuration

## Project Structure

```
backend/
├── config.py           # Configuration and environment variables
├── db.py              # PostgreSQL connection pooling
├── embedding.py       # Sentence transformer embeddings
├── tools.py           # Search, compare, category tools
├── qwen_client.py     # Ollama LLM interface
├── planner.py         # Main orchestration logic
├── main.py            # Application entry point
├── requirements.txt   # Python dependencies
└── .env.example       # Environment template
```

## Database Schema

### products
- `product_id` TEXT PRIMARY KEY
- `name` TEXT
- `brand` TEXT
- `price` NUMERIC
- `mrp` NUMERIC
- `sport` TEXT
- `category_level_1` TEXT
- `category_level_2` TEXT
- `description` TEXT
- `image_url` TEXT
- `product_url` TEXT
- `rating` NUMERIC
- `review_count` INTEGER

### product_embeddings
- `product_id` TEXT PRIMARY KEY → products(product_id)
- `embedding` vector(384)
- HNSW index on embedding

## Setup

### 1. Prerequisites

- Python 3.9+
- PostgreSQL with pgvector extension
- Ollama with Qwen 3:4B model

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

### 4. Install Ollama and Qwen

```bash
# Install Ollama: https://ollama.ai
# Pull Qwen model
ollama pull qwen2.5:3b
```

### 5. Verify Database

Ensure your PostgreSQL database has:
- pgvector extension installed
- ~9200 products in `products` table
- Embeddings in `product_embeddings` table
- HNSW index on embeddings

## Usage

### Interactive Mode

```bash
python main.py
```

Choose from:
1. Enter custom queries
2. Try example queries
3. Exit

### Example Queries

```
"I'm going camping with friends. What equipment do I need?"
"I want to start running. What should I buy?"
"Recommend badminton equipment under ₹5000"
"What's the best tent for 4 people?"
"Compare yoga mats under ₹2000"
```

## How It Works

### 1. User Query Processing

User submits a natural language query (e.g., "I need camping equipment")

### 2. Iterative Planning (max 3 iterations)

Qwen analyzes the query and decides on actions:

**Iteration 1**: Search for tents
```json
{"action": "search", "query": "camping tent 4 person"}
```

**Iteration 2**: Search for sleeping bags
```json
{"action": "search", "query": "sleeping bag", "sport": "camping"}
```

**Iteration 3**: Provide recommendations
```json
{
  "action": "answer",
  "essentials": ["Tent", "Sleeping Bag", "Headlamp"],
  "recommended_products": [...]
}
```

### 3. Tool Execution

Each action triggers Python tools:

- **hybrid_search()**: Generates embeddings → pgvector similarity search → SQL filtering
- **compare_products()**: Fetches detailed product info by IDs
- **get_categories()**: Returns available sports/categories

### 4. Response Generation

Qwen receives tool results and generates:
- Essential equipment list
- Optional items
- Specific product recommendations with reasoning
- Overall explanation

## API Functions

### Tools

```python
# Semantic + filtered search
hybrid_search(
    query="camping tent",
    sport="Camping",
    price_limit=5000,
    limit=10
)

# Get all categories
get_categories()

# Compare specific products
compare_products(["prod_1", "prod_2"])
```

### Planner

```python
result = shopping_planner("I want to start yoga")
# Returns recommendations with essentials, optional items, and products
```

## Configuration

Edit `config.py` or `.env`:

```python
# Database
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
POSTGRES_DB = "decathlon"

# Embedding Model
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# LLM
OLLAMA_MODEL = "qwen2.5:3b"

# Search
DEFAULT_SEARCH_LIMIT = 10
MAX_ITERATIONS = 3
```

## Optimization

### Database
- HNSW index provides fast approximate nearest neighbor search
- Connection pooling reduces overhead
- Parameterized queries prevent SQL injection

### Embeddings
- Model loaded once (singleton pattern)
- Batch processing support for multiple texts
- Normalized embeddings for cosine similarity

### LLM
- Lower temperature (0.3) for JSON responses
- Max token limit prevents runaway generation
- Structured prompts ensure valid JSON

## Logging

Logs are written to:
- `shopping_assistant.log` (file)
- stdout (console)

Log levels: DEBUG, INFO, WARNING, ERROR

## Error Handling

- Database connection failures → graceful degradation
- JSON parsing errors → retry with next iteration
- Tool failures → logged and skipped
- Max iterations → returns partial results

## Production Considerations

1. **Scale**: Current setup handles ~10k products efficiently
2. **Monitoring**: Add metrics for query latency, tool usage
3. **Caching**: Consider caching frequent embeddings
4. **Rate Limiting**: Add request throttling for API endpoints
5. **Authentication**: Implement user auth for production
6. **A/B Testing**: Test different LLM prompts and parameters

## REST API Endpoints

### Health Check
```bash
GET /health
```
Response:
```json
{
  "status": "healthy",
  "service": "decathlon-shopping-assistant"
}
```

### Chat Endpoint
```bash
POST /api/v1/chat
Content-Type: application/json

{
  "query": "I want to go camping"
}
```

Response:
```json
{
  "status": "success",
  "user_query": "I want to go camping",
  "essentials": ["Tent", "Sleeping Bag", "Headlamp"],
  "optional": ["Camping Chair", "Cooler"],
  "recommended_products": [
    {
      "product_id": "...",
      "name": "...",
      "price": 4999,
      "rating": 4.5,
      "reason": "High-rated 4-person tent with excellent reviews"
    }
  ],
  "reasoning": "For camping, you'll need shelter, sleeping gear...",
  "iterations": 2
}
```

### Search Endpoint
```bash
POST /api/v1/search
Content-Type: application/json

{
  "query": "running shoes",
  "sport": "Running",
  "price_limit": 5000,
  "limit": 10
}
```

Response:
```json
{
  "query": "running shoes",
  "count": 10,
  "results": [
    {
      "product_id": "...",
      "name": "...",
      "brand": "...",
      "price": 3499,
      "rating": 4.3,
      "similarity_score": 0.85
    }
  ]
}
```

### Categories Endpoint
```bash
GET /api/v1/categories
```

Response:
```json
{
  "count": 150,
  "categories": [
    {
      "sport": "Camping",
      "category_level_1": "Shelter",
      "category_level_2": "Tent"
    }
  ]
}
```

### Compare Endpoint
```bash
POST /api/v1/compare
Content-Type: application/json

{
  "product_ids": ["prod1", "prod2", "prod3"]
}
```

Response:
```json
{
  "count": 3,
  "products": [
    {
      "product_id": "prod1",
      "name": "...",
      "price": 2999,
      "rating": 4.5,
      "description": "..."
    }
  ]
}
```

## Testing with cURL

```bash
# Health check
curl http://localhost:5000/health

# Chat
curl -X POST http://localhost:5000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "I need yoga equipment"}'

# Search
curl -X POST http://localhost:5000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "yoga mat", "price_limit": 2000}'

# Categories
curl http://localhost:5000/api/v1/categories

# Compare
curl -X POST http://localhost:5000/api/v1/compare \
  -H "Content-Type: application/json" \
  -d '{"product_ids": ["id1", "id2"]}'
```

## Frontend Integration

Open `example_client.html` in a browser for a ready-to-use web interface.

The HTML client demonstrates:
- Real-time chat interface
- Example query buttons
- Product card rendering
- Error handling
- Loading states

## Troubleshooting

### Connection Errors
- Verify PostgreSQL credentials in `.env`
- Check pgvector extension: `SELECT * FROM pg_extension WHERE extname = 'vector';`

### Empty Results
- Verify embeddings exist: `SELECT COUNT(*) FROM product_embeddings;`
- Check HNSW index: `\d product_embeddings`

### LLM Issues
- Ensure Ollama is running: `ollama list`
- Verify model: `ollama run qwen3:4b`

### Slow Queries
- Check index usage: `EXPLAIN ANALYZE SELECT ...`
- Verify HNSW parameters
- Monitor connection pool

### CORS Issues
- The API includes CORS support via flask-cors
- For production, configure allowed origins in `api.py`

## Documentation

- **SETUP.md**: Detailed setup instructions
- **DEPLOYMENT.md**: Production deployment guide
- **example_client.html**: Frontend demo

## License

MIT
