"""
Decathlon Smart Shopping API - Production Version
Qwen2.5-1.5B-Instruct + PostgreSQL + pgvector + Hybrid Search
"""
from flask import Flask, request
from flask_restx import Api, Resource, fields
from flask_cors import CORS
import logging
import os
import traceback
from functools import wraps
from tools import hybrid_search, get_categories, compare_products
from db import initialize_pool, close_pool
from embedding import load_model as load_embedding_model
import atexit
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Production uses HuggingFace Qwen2.5-1.5B-Instruct with LoRA fine-tuning
logger.info("🚀 Starting API with HuggingFace Qwen2.5-1.5B-Instruct")
from hf_planner import shopping_planner_hf, parse_query_with_qwen, load_fine_tuned_model
logger.info("✓ HuggingFace planner imported successfully")

API_KEY = os.getenv('API_KEY', 'decathlon_smart_search_2024_secure_key_abc123xyz')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('Api-Key')
        
        if not provided_key:
            return {'error': 'Unauthorized', 'message': 'API key required'}, 401
        
        if provided_key != API_KEY:
            return {'error': 'Forbidden', 'message': 'Invalid API key'}, 403
        
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
CORS(app)

api = Api(
    app,
    version='1.0.0',
    title='Decathlon Smart Shopping API',
    description='AI-powered shopping search with Qwen2.5-1.5B-Instruct + PostgreSQL + pgvector',
    doc='/docs',
    prefix='/api/v1',
    authorizations={
        'apiKey': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'API-KEY'
        }
    },
    security='apiKey'
)

# Global initialization flags
_initialized = False
_model_loaded = False

def initialize():
    """
    Initialize application resources exactly once.
    Loads: PostgreSQL pool, embeddings, HF model
    """
    global _initialized, _model_loaded
    
    if _initialized:
        logger.debug("⏭️  Already initialized, skipping...")
        return
    
    logger.info("=" * 80)
    logger.info("🔧 INITIALIZING BACKEND")
    logger.info("=" * 80)
    
    try:
        # Step 1: Database connection pool
        logger.info("1️⃣  Initializing PostgreSQL connection pool...")
        initialize_pool(minconn=2, maxconn=20)
        logger.info("✓ PostgreSQL pool ready")
        
        # Step 2: Embedding model
        logger.info("2️⃣  Loading sentence-transformers embedding model...")
        logger.info("   Model: BAAI/bge-small-en-v1.5")
        load_embedding_model()
        logger.info("✓ Embedding model loaded")
        
        _initialized = True
        logger.info("✓ Backend initialization complete")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ INITIALIZATION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        raise

def initialize_model():
    """
    Pre-load the fine-tuned HF model (separate from basic initialization).
    This is optional and can be deferred to first use.
    """
    global _model_loaded
    
    if _model_loaded:
        logger.debug("⏭️  Model already loaded, skipping...")
        return
    
    logger.info("=" * 80)
    logger.info("🤖 LOADING FINE-TUNED MODEL")
    logger.info("=" * 80)
    
    try:
        logger.info("📦 Loading Qwen2.5-1.5B-Instruct with LoRA adapter...")
        logger.info("   Using: HuggingFace + PEFT")
        logger.info("   Adapter: training/outputs/qwen25_1_5b_lora_hf/")
        
        load_fine_tuned_model()
        
        _model_loaded = True
        logger.info("✓ Fine-tuned model loaded and ready")
        logger.info("=" * 80)
        
    except FileNotFoundError as e:
        logger.error("=" * 80)
        logger.error("❌ MODEL NOT FOUND")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("The fine-tuned LoRA adapter was not found")
        logger.error("Expected: training/outputs/qwen3_4b_hf/")
        _model_loaded = False
        raise
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ MODEL LOADING FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        _model_loaded = False
        raise

atexit.register(close_pool)

# Define API namespaces
ns_shopping = api.namespace('shopping', description='Shopping and search operations')
ns_products = api.namespace('products', description='Product information')
ns_system = api.namespace('system', description='System health')

# Request/response models
search_request = api.model('SearchRequest', {
    'query': fields.String(required=True, description='Search query', example='yoga mat'),
    'sport': fields.String(description='Filter by sport', example='Yoga'),
    'price_limit': fields.Float(description='Max price', example=2000.0),
    'limit': fields.Integer(description='Result limit', default=10, example=5)
})

smart_search_request = api.model('SmartSearchRequest', {
    'query': fields.String(required=True, description='Natural language query', 
                          example='Horse riding boots for kids below 3000')
})

parse_query_request = api.model('ParseQueryRequest', {
    'query': fields.String(required=True, description='Query to parse', 
                          example='Horse riding boots for kids below 3000')
})

product_model = api.model('Product', {
    'product_id': fields.String(description='Product ID'),
    'name': fields.String(description='Product name'),
    'brand': fields.String(description='Brand'),
    'price': fields.Float(description='Price in INR'),
    'sport': fields.String(description='Sport category'),
    'rating': fields.Float(description='Rating (0-5)'),
    'similarity_score': fields.Float(description='Similarity (0-1)')
})

search_response = api.model('SearchResponse', {
    'query': fields.String(description='Original query'),
    'count': fields.Integer(description='Result count'),
    'results': fields.List(fields.Nested(product_model))
})

smart_search_response = api.model('SmartSearchResponse', {
    'status': fields.String(description='Status', example='success'),
    'user_query': fields.String(description='Original query'),
    'parsed_query': fields.Raw(description='Structured query'),
    'intent': fields.String(description='Intent', example='search'),
    'recommendations': fields.String(description='AI recommendations'),
    'products': fields.List(fields.Nested(product_model)),
    'metadata': fields.Raw(description='Metadata')
})

parse_query_response = api.model('ParseQueryResponse', {
    'status': fields.String(description='Status'),
    'user_query': fields.String(description='Original query'),
    'parsed_query': fields.Raw(description='Parsed JSON'),
    'intent': fields.String(description='Intent'),
    'metadata': fields.Raw(description='Metadata')
})

error_response = api.model('ErrorResponse', {
    'error': fields.String(description='Error type'),
    'message': fields.String(description='Error message')
})


@ns_shopping.route('/search')
class Search(Resource):
    @api.doc('search_products')
    @api.expect(search_request)
    @api.marshal_with(search_response, code=200)
    @api.response(400, 'Bad Request', error_response)
    @api.response(500, 'Internal Server Error', error_response)
    def post(self):
        """Semantic product search with optional filters"""
        initialize()
        try:
            data = request.get_json()
            
            if not data or 'query' not in data:
                return {'error': 'Missing field', 'message': "'query' required"}, 400
            
            query = data['query']
            sport = data.get('sport')
            price_limit = data.get('price_limit')
            limit = data.get('limit', 10)
            
            logger.info(f"🔍 Search: {query}")
            results = hybrid_search(query, sport=sport, price_limit=price_limit, limit=limit)
            logger.info(f"✓ Found {len(results)} products")
            
            return {
                'query': query,
                'count': len(results),
                'results': results
            }, 200
            
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            logger.error(traceback.format_exc())
            return {'error': 'Internal server error', 'message': str(e)}, 500


@ns_shopping.route('/smart-search')
class SmartSearch(Resource):
    @api.doc('smart_search', security='apiKey')
    @api.expect(smart_search_request)
    @api.marshal_with(smart_search_response, code=200)
    @api.response(401, 'Unauthorized', error_response)
    @api.response(403, 'Forbidden', error_response)
    @api.response(400, 'Bad Request', error_response)
    @api.response(500, 'Internal Server Error', error_response)
    @api.response(503, 'Service Unavailable', error_response)
    @require_api_key
    def post(self):
        """
        AI-powered smart search with Qwen2.5-1.5B-Instruct
        
        Pipeline:
        1. Qwen2.5-1.5B-Instruct parses query → Structured JSON
        2. Hybrid search: Keyword + Semantic (pgvector)
        3. Qwen2.5-1.5B-Instruct generates natural language response
        """
        initialize()
        initialize_model()
        
        try:
            data = request.get_json()
            
            if not data or 'query' not in data:
                return {'error': 'Missing field', 'message': "'query' required"}, 400
            
            user_query = data['query'].strip()
            
            if not user_query:
                return {'error': 'Invalid input', 'message': 'Query cannot be empty'}, 400
            
            logger.info("=" * 80)
            logger.info(f"🧠 SMART SEARCH REQUEST")
            logger.info(f"Query: {user_query}")
            logger.info("=" * 80)
            
            # Use complete HuggingFace planner pipeline
            result = shopping_planner_hf(user_query)
            
            if result.get('status') == 'error':
                logger.error(f"❌ Planner returned error: {result.get('error')}")
                return {
                    'error': 'Search failed',
                    'message': result.get('error', 'Unknown error')
                }, 500
            
            products_found = result.get('metadata', {}).get('products_found', 0)
            logger.info(f"✓ Smart search complete: {products_found} products")
            logger.info("=" * 80)
            
            return result, 200
            
        except FileNotFoundError as e:
            logger.error("=" * 80)
            logger.error("❌ MODEL NOT FOUND")
            logger.error(f"Error: {e}")
            logger.error("=" * 80)
            return {
                'error': 'Model not found',
                'message': 'Fine-tuned model not available'
            }, 503
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error("❌ SMART SEARCH ERROR")
            logger.error(f"Error: {e}")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            return {'error': 'Internal server error', 'message': str(e)}, 500


@ns_shopping.route('/parse-query')
class ParseQuery(Resource):
    @api.doc('parse_query')
    @api.expect(parse_query_request)
    @api.marshal_with(parse_query_response, code=200)
    @api.response(400, 'Bad Request', error_response)
    @api.response(500, 'Internal Server Error', error_response)
    @api.response(503, 'Service Unavailable', error_response)
    def post(self):
        """
        Parse natural language query to structured JSON
        
        Uses fine-tuned Qwen2.5-1.5B-Instruct to extract:
        - Sport category
        - Product category
        - Keywords
        - Price limit
        - Experience level
        """
        initialize()
        initialize_model()
        
        try:
            data = request.get_json()
            
            if not data or 'query' not in data:
                return {'error': 'Missing field', 'message': "'query' required"}, 400
            
            user_query = data['query'].strip()
            
            if not user_query:
                return {'error': 'Invalid input', 'message': 'Query cannot be empty'}, 400
            
            logger.info(f"🧩 Parse query request: {user_query}")
            
            import time
            start_time = time.time()
            
            logger.info("📤 Calling parse_query_with_qwen...")
            parsed_query = parse_query_with_qwen(user_query)
            logger.info("📥 Parse function returned")
            
            parse_time_ms = int((time.time() - start_time) * 1000)
            
            if not parsed_query:
                logger.error("❌ Parser returned None")
                return {
                    'error': 'Parse failed',
                    'message': 'Failed to parse query'
                }, 500
            
            response = {
                'status': 'success',
                'user_query': user_query,
                'parsed_query': parsed_query,
                'intent': parsed_query.get('intent', 'unknown'),
                'metadata': {
                    'model': 'Qwen2.5-1.5B-Instruct (HuggingFace + PEFT)',
                    'parse_time_ms': parse_time_ms
                }
            }
            
            logger.info(f"✓ Parse complete: intent={response['intent']}, time={parse_time_ms}ms")
            return response, 200
            
        except FileNotFoundError as e:
            logger.error(f"❌ Model not found: {e}")
            return {
                'error': 'Model not found',
                'message': 'Fine-tuned model not available'
            }, 503
            
        except Exception as e:
            logger.error(f"❌ Parse error: {e}")
            logger.error(traceback.format_exc())
            return {'error': 'Internal server error', 'message': str(e)}, 500


@ns_products.route('/categories')
class Categories(Resource):
    @api.doc('get_categories')
    def get(self):
        """Get all available sports and category combinations"""
        initialize()
        try:
            results = get_categories()
            return {'count': len(results), 'categories': results}, 200
        except Exception as e:
            logger.error(f"Categories error: {e}", exc_info=True)
            return {'error': 'Internal server error', 'message': str(e)}, 500


@ns_system.route('/health')
class Health(Resource):
    @api.doc('health_check')
    def get(self):
        """Health check endpoint - does NOT initialize models"""
        return {
            'status': 'healthy',
            'version': '1.0.0',
            'planner': 'HuggingFace + PEFT'
        }, 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    preload_model = os.environ.get("PRELOAD_MODEL", "false").lower() == "true"
    
    logger.info(f"🚀 Starting Flask app on 0.0.0.0:{port}")
    logger.info(f"   PRELOAD_MODEL={preload_model}")
    
    # Optional: Pre-load model at startup
    if preload_model:
        logger.info("🤖 Pre-loading model at startup...")
        try:
            initialize()
            initialize_model()
            logger.info("✓ Model pre-loaded successfully")
        except Exception as e:
            logger.error(f"⚠️  Model pre-load failed: {e}")
            logger.info("   Model will load on first request instead")
    else:
        logger.info("⏭️  Skipping model pre-load (will load on first request)")
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
