"""
Decathlon Smart Shopping API - Single Public Endpoint
Qwen3-4B + PostgreSQL + pgvector

Architecture:
    User → api_swagger.py → local_model_server.py → Tools → PostgreSQL
"""
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from flask_cors import CORS
import logging
import os
import requests
import traceback
from functools import wraps
from database import initialize_pool, close_pool
import atexit
from dotenv import load_dotenv

# Import Tools
from tools.search_tool import SearchTool
from tools.task_tool import TaskTool
from tools.compare_tool import CompareTool
from tools.alternatives_tool import AlternativesTool

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
API_KEY = os.getenv('API_KEY', 'decathlon_smart_search_2024_secure_key_abc123xyz')
LOCAL_MODEL_URL = os.getenv('LOCAL_MODEL_URL', 'http://localhost:8000')

logger.info("🚀 Starting Decathlon Smart Shopping API")
logger.info(f"   Model Server: {LOCAL_MODEL_URL}")


# ============================================================================
# LOCAL MODEL CLIENT
# ============================================================================

class LocalModelClient:
    """
    Client for communicating with local_model_server.py
    
    Sends natural language queries and receives structured JSON.
    """
    
    def __init__(self, base_url=None, timeout=30):
        self.base_url = base_url or LOCAL_MODEL_URL
        self.timeout = timeout
        logger.info(f"LocalModelClient initialized: {self.base_url}")
    
    def parse(self, query: str) -> dict:
        """
        Parse natural language query into structured JSON.
        
        Args:
            query: Natural language query
        
        Returns:
            Structured JSON dict with intent and parameters
        
        Raises:
            ConnectionError: If cannot connect to model server
            TimeoutError: If request times out
            ValueError: If response is invalid JSON
        """
        try:
            logger.info(f"Parsing query: {query}")
            
            # Call local model server
            response = requests.post(
                f"{self.base_url}/parse-query",
                json={"query": query},
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Model server error: {response.status_code}")
                logger.error(f"Response: {response.text}")
                raise ValueError(f"Model server returned {response.status_code}")
            
            # Parse JSON
            result = response.json()
            
            logger.info(f"✓ Parsed intent: {result.get('intent')}")
            
            return result
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to model server: {e}")
            raise ConnectionError(
                f"Cannot connect to model server at {self.base_url}. "
                f"Is local_model_server.py running?"
            )
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError(f"Model server request timed out after {self.timeout}s")
        except ValueError as e:
            logger.error(f"Invalid JSON from model server: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

# Initialize client and tools
model_client = LocalModelClient()
search_tool = SearchTool()
task_tool = TaskTool()
compare_tool = CompareTool()
alternatives_tool = AlternativesTool()


# ============================================================================
# FLASK APP & API
# ============================================================================

def require_api_key(f):
    """API key authentication decorator"""
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
    version='3.2.0',
    title='Decathlon Smart Shopping API',
    description='''
    Unified API for natural language shopping queries with debug endpoints.
    
    **Production Endpoint:**
        POST /api/v1/query - Full pipeline (NL → SLM → Tools → Results)
    
    **Debug Endpoints:**
        POST /api/v1/debug/parse-query - Test SLM output only
        POST /api/v1/debug/search - Test SearchTool directly
        POST /api/v1/debug/task - Test TaskTool directly
        POST /api/v1/debug/compare - Test CompareTool directly
        POST /api/v1/debug/alternatives - Test AlternativesTool directly
        POST /api/v1/debug/embedding - Test local embedding generation
    
    **Architecture:**
        User → /api/v1/query → Local Model Server → Tools → PostgreSQL
    
    **Supported queries:**
        - "running shoes under 5000" (search)
        - "I want to start playing golf" (task)
        - "compare MH500 and NH500" (compare)
        - "alternatives to MH500" (alternatives)
    ''',
    doc='/docs',
    prefix='/api/v1',
    authorizations={
        'apiKey': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Api-Key'
        }
    },
    security='apiKey'
)

# Global initialization
_initialized = False


def initialize():
    """Initialize application resources"""
    global _initialized
    
    if _initialized:
        return
    
    logger.info("=" * 80)
    logger.info("INITIALIZING API")
    logger.info("=" * 80)
    
    try:
        # Initialize database
        logger.info("Initializing PostgreSQL connection pool...")
        initialize_pool(minconn=2, maxconn=20)
        logger.info("✓ PostgreSQL ready")
        
        # Check model server
        logger.info("Checking model server...")
        try:
            response = requests.get(f"{LOCAL_MODEL_URL}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                logger.info(f"✓ Model server connected")
                logger.info(f"   Model: {health.get('model', 'unknown')}")
                logger.info(f"   Device: {health.get('device', 'unknown')}")
            else:
                logger.warning(f"⚠️  Model server unhealthy: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  Model server not reachable: {e}")
            logger.warning("   Queries will fail until server is started")
        
        _initialized = True
        
        logger.info("=" * 80)
        logger.info("✅ API READY")
        logger.info("=" * 80)
        logger.info("Production Endpoint:")
        logger.info("  POST /api/v1/query")
        logger.info("")
        logger.info("Debug Endpoints:")
        logger.info("  POST /api/v1/debug/parse-query")
        logger.info("  POST /api/v1/debug/search")
        logger.info("  POST /api/v1/debug/task")
        logger.info("  POST /api/v1/debug/compare")
        logger.info("  POST /api/v1/debug/alternatives")
        logger.info("  POST /api/v1/debug/embedding")
        logger.info("")
        logger.info("System:")
        logger.info("  GET  /api/v1/system/health")
        logger.info("  GET  /docs (Swagger UI)")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        logger.error(traceback.format_exc())
        raise


atexit.register(close_pool)

# Namespaces
ns_query = api.namespace('query', description='Main query endpoint')
ns_system = api.namespace('system', description='System endpoints')
ns_debug = api.namespace('debug', description='Debug endpoints for testing individual components')

# Request/Response models
query_request = api.model('QueryRequest', {
    'query': fields.String(
        required=True,
        description='Natural language query',
        example='running shoes under 5000'
    )
})

parse_query_request = api.model('ParseQueryRequest', {
    'query': fields.String(
        required=True,
        description='Natural language query to parse',
        example='running shoes under 5000'
    )
})

search_request = api.model('SearchRequest', {
    'sport': fields.String(required=True, description='Sport category', example='Running'),
    'category_level_1': fields.String(required=False, description='Category level 1', example='Footwear'),
    'category_level_2': fields.String(required=False, description='Category level 2'),
    'keywords': fields.List(fields.String, required=False, description='Search keywords', example=['running', 'shoes']),
    'price_limit': fields.Float(required=False, description='Maximum price', example=5000)
})

task_request = api.model('TaskRequest', {
    'activity': fields.String(required=True, description='Activity name', example='Golf'),
    'budget': fields.Float(required=False, description='Total budget', example=10000)
})

compare_request = api.model('CompareRequest', {
    'products': fields.List(fields.String, required=True, description='Product IDs', example=['MH500', 'NH500'])
})

alternatives_request = api.model('AlternativesRequest', {
    'product': fields.String(required=True, description='Product ID', example='MH500')
})

embedding_request = api.model('EmbeddingRequest', {
    'text': fields.String(required=True, description='Text to embed', example='running shoes')
})


# ============================================================================
# ENDPOINTS
# ============================================================================

@ns_query.route('')
class QueryEndpoint(Resource):
    """Single unified query endpoint"""
    
    @api.doc('execute_query')
    @api.expect(query_request)
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(401, 'Unauthorized')
    @api.response(500, 'Internal Server Error')
    @require_api_key
    def post(self):
        """
        Execute natural language query
        
        Examples:
        - "running shoes under 5000"
        - "waterproof hiking shoes"
        - "I want to start playing golf"
        - "golf equipment under 15000"
        - "compare MH500 and NH500"
        - "alternatives to MH500"
        """
        # Initialize
        initialize()
        
        try:
            data = request.get_json()
            
            if not data or 'query' not in data:
                return {
                    'error': 'Bad Request',
                    'message': 'Query field required'
                }, 400
            
            user_query = data['query'].strip()
            
            if not user_query:
                return {
                    'error': 'Bad Request',
                    'message': 'Query cannot be empty'
                }, 400
            
            logger.info(f"Processing query: {user_query}")
            
            # Step 1: Parse query with local model server
            try:
                parsed = model_client.parse(user_query)
            except ConnectionError as e:
                return {
                    'error': 'Service Unavailable',
                    'message': str(e)
                }, 503
            except TimeoutError as e:
                return {
                    'error': 'Gateway Timeout',
                    'message': str(e)
                }, 504
            except Exception as e:
                return {
                    'error': 'Bad Gateway',
                    'message': f'Model server error: {str(e)}'
                }, 502
            
            intent = parsed.get('intent')
            
            if not intent:
                return {
                    'error': 'Bad Request',
                    'message': 'Invalid response from model server (missing intent)'
                }, 400
            
            logger.info(f"Intent: {intent}")
            
            # Step 2: Route to appropriate tool
            try:
                if intent == 'search':
                    from models.schemas import SearchRequest
                    search_request = SearchRequest(**parsed['search_request'])
                    result = search_tool.execute(search_request)
                    
                elif intent == 'task':
                    from models.schemas import TaskArguments
                    task_arguments = TaskArguments(**parsed['arguments'])
                    result = task_tool.execute(task_arguments)
                    
                elif intent == 'compare':
                    from models.schemas import CompareArguments
                    compare_arguments = CompareArguments(**parsed['arguments'])
                    result = compare_tool.execute(compare_arguments)
                    
                elif intent == 'alternatives':
                    from models.schemas import AlternativesArguments
                    alternatives_arguments = AlternativesArguments(**parsed['arguments'])
                    result = alternatives_tool.execute(alternatives_arguments)
                
                else:
                    return {
                        'error': 'Bad Request',
                        'message': f'Unknown intent: {intent}'
                    }, 400
                
                # Step 3: Return result
                response = result.dict()
                response['query'] = user_query
                
                logger.info(f"✓ Query processed successfully")
                
                return response, 200
                
            except ValueError as e:
                logger.error(f"Validation error: {e}")
                return {
                    'error': 'Bad Request',
                    'message': str(e)
                }, 400
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                logger.error(traceback.format_exc())
                return {
                    'error': 'Internal Server Error',
                    'message': str(e)
                }, 500
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            return {
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred'
            }, 500


@ns_system.route('/health')
class HealthEndpoint(Resource):
    """System health check"""
    
    @api.doc('health_check')
    def get(self):
        """
        Check system health
        
        Returns status of:
        - Model server connection
        - Database connection
        """
        health_status = {
            'status': 'healthy',
            'api': 'running',
            'model_server': 'unknown',
            'database': 'unknown'
        }
        
        # Check model server
        try:
            response = requests.get(f"{LOCAL_MODEL_URL}/health", timeout=5)
            if response.status_code == 200:
                health_status['model_server'] = 'connected'
                model_info = response.json()
                health_status['model'] = model_info.get('model', 'unknown')
            else:
                health_status['model_server'] = 'unhealthy'
                health_status['status'] = 'degraded'
        except:
            health_status['model_server'] = 'disconnected'
            health_status['status'] = 'degraded'
        
        # Check database
        try:
            from database import connect_db, release_connection
            conn = connect_db()
            release_connection(conn)
            health_status['database'] = 'connected'
        except:
            health_status['database'] = 'disconnected'
            health_status['status'] = 'unhealthy'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return health_status, status_code


@ns_system.route('/categories')
class CategoriesEndpoint(Resource):
    """Knowledge base category explorer"""
    
    @api.doc('get_categories')
    @api.response(200, 'Success')
    @api.response(500, 'Database error')
    def get(self):
        """
        Get all product categories in the knowledge base.
        
        Returns a structured breakdown of:
        - All sports with total product counts
        - Category level 1 and 2 combinations per sport
        - Price ranges per category
        - Summary statistics
        
        Useful for:
        - Exploring what products are in the KB
        - Training data generation
        - Frontend category browsing
        """
        try:
            from database import connect_db, release_connection
            from psycopg2.extras import RealDictCursor

            conn = connect_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            try:
                # Per-sport summary
                cur.execute("""
                    SELECT
                        sport,
                        COUNT(*) AS product_count,
                        ROUND(MIN(price)::numeric, 0) AS min_price,
                        ROUND(MAX(price)::numeric, 0) AS max_price,
                        ROUND(AVG(price)::numeric, 0) AS avg_price
                    FROM products
                    WHERE sport IS NOT NULL AND sport != ''
                    GROUP BY sport
                    ORDER BY product_count DESC
                """)
                sports_raw = cur.fetchall()

                # Per-sport + category breakdown
                cur.execute("""
                    SELECT
                        COALESCE(sport, '') AS sport,
                        COALESCE(category_level_1, '') AS category_level_1,
                        COALESCE(category_level_2, '') AS category_level_2,
                        COUNT(*) AS product_count,
                        ROUND(MIN(price)::numeric, 0) AS min_price,
                        ROUND(MAX(price)::numeric, 0) AS max_price
                    FROM products
                    WHERE sport IS NOT NULL AND sport != ''
                    GROUP BY sport, category_level_1, category_level_2
                    ORDER BY sport, product_count DESC
                """)
                cats_raw = cur.fetchall()

                # Totals
                cur.execute("SELECT COUNT(*) AS total FROM products")
                total = cur.fetchone()['total']

                cur.execute("""
                    SELECT COUNT(*) AS total
                    FROM products
                    WHERE sport IS NOT NULL AND sport != ''
                """)
                with_sport = cur.fetchone()['total']

            finally:
                cur.close()
                release_connection(conn)

            # Build structured response grouped by sport
            sports_map = {}
            for row in sports_raw:
                sports_map[row['sport']] = {
                    'sport': row['sport'],
                    'product_count': row['product_count'],
                    'price_range': {
                        'min': float(row['min_price']) if row['min_price'] else None,
                        'max': float(row['max_price']) if row['max_price'] else None,
                        'avg': float(row['avg_price']) if row['avg_price'] else None
                    },
                    'categories': []
                }

            for row in cats_raw:
                sport = row['sport']
                if sport in sports_map:
                    sports_map[sport]['categories'].append({
                        'category_level_1': row['category_level_1'] or None,
                        'category_level_2': row['category_level_2'] or None,
                        'product_count': row['product_count'],
                        'price_range': {
                            'min': float(row['min_price']) if row['min_price'] else None,
                            'max': float(row['max_price']) if row['max_price'] else None
                        }
                    })

            return {
                'summary': {
                    'total_products': total,
                    'products_with_sport': with_sport,
                    'products_without_sport': total - with_sport,
                    'total_sports': len(sports_map)
                },
                'sports': list(sports_map.values())
            }, 200

        except Exception as e:
            logger.error(f"Categories endpoint error: {e}")
            return {'error': str(e)}, 500


# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@ns_debug.route('/parse-query')
class ParseQueryEndpoint(Resource):
    """Debug endpoint: Test SLM output only"""
    
    @api.doc('parse_query_debug')
    @api.expect(parse_query_request)
    @api.response(200, 'Success')
    @api.response(503, 'Model server unavailable')
    @require_api_key
    def post(self):
        """
        Parse natural language query using SLM (debug)
        
        Returns ONLY the structured JSON from the model server.
        Does NOT execute any tools.
        
        Useful for testing:
        - Model server connectivity
        - Intent classification accuracy
        - Parameter extraction
        """
        initialize()
        
        try:
            data = request.get_json()
            
            if not data or 'query' not in data:
                return {'error': 'Query field required'}, 400
            
            user_query = data['query'].strip()
            
            if not user_query:
                return {'error': 'Query cannot be empty'}, 400
            
            logger.info(f"[DEBUG] Parsing query: {user_query}")
            
            # Call model server directly
            try:
                parsed = model_client.parse(user_query)
                logger.info(f"[DEBUG] ✓ Parsed successfully")
                return parsed, 200
                
            except ConnectionError as e:
                return {'error': 'Service Unavailable', 'message': str(e)}, 503
            except TimeoutError as e:
                return {'error': 'Gateway Timeout', 'message': str(e)}, 504
            except Exception as e:
                return {'error': 'Model server error', 'message': str(e)}, 502
        
        except Exception as e:
            logger.error(f"[DEBUG] Parse query error: {e}")
            return {'error': str(e)}, 500


@ns_debug.route('/search')
class SearchDebugEndpoint(Resource):
    """Debug endpoint: Test SearchTool directly"""
    
    @api.doc('search_debug')
    @api.expect(search_request)
    @api.response(200, 'Success')
    @require_api_key
    def post(self):
        """
        Execute SearchTool directly (debug)
        
        Bypasses SLM - accepts structured search parameters directly.
        
        Useful for testing:
        - HybridSearch functionality
        - Database queries
        - Product filtering and ranking
        """
        initialize()
        
        try:
            data = request.get_json()
            
            logger.info(f"[DEBUG] SearchTool with params: {data}")
            
            from models.schemas import SearchRequest
            search_request_obj = SearchRequest(**data)
            result = search_tool.execute(search_request_obj)
            
            logger.info(f"[DEBUG] ✓ SearchTool returned {result.total} products")
            
            return result.dict(), 200
            
        except ValueError as e:
            logger.error(f"[DEBUG] Validation error: {e}")
            return {'error': 'Validation error', 'message': str(e)}, 400
        except Exception as e:
            logger.error(f"[DEBUG] SearchTool error: {e}")
            logger.error(traceback.format_exc())
            return {'error': str(e)}, 500


@ns_debug.route('/task')
class TaskDebugEndpoint(Resource):
    """Debug endpoint: Test TaskTool directly"""
    
    @api.doc('task_debug')
    @api.expect(task_request)
    @api.response(200, 'Success')
    @require_api_key
    def post(self):
        """
        Execute TaskTool directly (debug)
        
        Bypasses SLM - accepts activity and budget directly.
        
        Useful for testing:
        - Task item generation
        - Product search for each item
        - Budget optimizer
        - Item selection logic
        """
        initialize()
        
        try:
            data = request.get_json()
            
            logger.info(f"[DEBUG] TaskTool with params: {data}")
            
            from models.schemas import TaskArguments
            task_arguments = TaskArguments(**data)
            result = task_tool.execute(task_arguments)
            
            logger.info(f"[DEBUG] ✓ TaskTool returned {len(result.items)} items")
            if result.total_cost:
                logger.info(f"[DEBUG]   Total cost: ₹{result.total_cost}")
            
            return result.dict(), 200
            
        except ValueError as e:
            logger.error(f"[DEBUG] Validation error: {e}")
            return {'error': 'Validation error', 'message': str(e)}, 400
        except Exception as e:
            logger.error(f"[DEBUG] TaskTool error: {e}")
            logger.error(traceback.format_exc())
            return {'error': str(e)}, 500


@ns_debug.route('/compare')
class CompareDebugEndpoint(Resource):
    """Debug endpoint: Test CompareTool directly"""
    
    @api.doc('compare_debug')
    @api.expect(compare_request)
    @api.response(200, 'Success')
    @require_api_key
    def post(self):
        """
        Execute CompareTool directly (debug)
        
        Bypasses SLM - accepts product IDs directly.
        
        Useful for testing:
        - Product retrieval by ID
        - Database queries
        - Product data completeness
        """
        initialize()
        
        try:
            data = request.get_json()
            
            logger.info(f"[DEBUG] CompareTool with params: {data}")
            
            from models.schemas import CompareArguments
            compare_arguments = CompareArguments(**data)
            result = compare_tool.execute(compare_arguments)
            
            logger.info(f"[DEBUG] ✓ CompareTool returned {len(result.products)} products")
            
            return result.dict(), 200
            
        except ValueError as e:
            logger.error(f"[DEBUG] Validation error: {e}")
            return {'error': 'Validation error', 'message': str(e)}, 400
        except Exception as e:
            logger.error(f"[DEBUG] CompareTool error: {e}")
            logger.error(traceback.format_exc())
            return {'error': str(e)}, 500


@ns_debug.route('/alternatives')
class AlternativesDebugEndpoint(Resource):
    """Debug endpoint: Test AlternativesTool directly"""
    
    @api.doc('alternatives_debug')
    @api.expect(alternatives_request)
    @api.response(200, 'Success')
    @require_api_key
    def post(self):
        """
        Execute AlternativesTool directly (debug)
        
        Bypasses SLM - accepts product ID directly.
        
        Useful for testing:
        - Alternative product discovery
        - Similarity logic
        - Price range filtering
        """
        initialize()
        
        try:
            data = request.get_json()
            
            logger.info(f"[DEBUG] AlternativesTool with params: {data}")
            
            from models.schemas import AlternativesArguments
            alternatives_arguments = AlternativesArguments(**data)
            result = alternatives_tool.execute(alternatives_arguments)
            
            logger.info(f"[DEBUG] ✓ AlternativesTool returned {result.total} alternatives")
            
            return result.dict(), 200
            
        except ValueError as e:
            logger.error(f"[DEBUG] Validation error: {e}")
            return {'error': 'Validation error', 'message': str(e)}, 400
        except Exception as e:
            logger.error(f"[DEBUG] AlternativesTool error: {e}")
            logger.error(traceback.format_exc())
            return {'error': str(e)}, 500


@ns_debug.route('/embedding')
class EmbeddingDebugEndpoint(Resource):
    """Debug endpoint: Test local embedding generation"""
    
    @api.doc('embedding_debug')
    @api.expect(embedding_request)
    @api.response(200, 'Success')
    @require_api_key
    def post(self):
        """
        Generate embedding for text (debug)
        
        Tests local sentence-transformers embedding generation.
        NO HTTP calls to model server.
        
        Useful for testing:
        - Embedding service functionality
        - Embedding dimensions (384)
        - Vector normalization
        """
        initialize()
        
        try:
            data = request.get_json()
            
            if not data or 'text' not in data:
                return {'error': 'Text field required'}, 400
            
            text = data['text'].strip()
            
            if not text:
                return {'error': 'Text cannot be empty'}, 400
            
            logger.info(f"[DEBUG] Generating embedding for: {text}")
            
            # Import embedding module
            from embedding import get_embedding
            
            # Generate embedding
            embedding = get_embedding(text)
            
            # Calculate norm to verify normalization
            import numpy as np
            norm = float(np.linalg.norm(embedding))
            
            logger.info(f"[DEBUG] ✓ Embedding generated")
            logger.info(f"[DEBUG]   Dimension: {len(embedding)}")
            logger.info(f"[DEBUG]   Norm: {norm:.6f}")
            
            return {
                'text': text,
                'dimension': len(embedding),
                'embedding_preview': embedding[:10],  # First 10 values
                'norm': norm,
                'model': 'sentence-transformers/all-MiniLM-L6-v2',
                'note': 'Embedding generated locally (no HTTP call to model server)'
            }, 200
            
        except Exception as e:
            logger.error(f"[DEBUG] Embedding error: {e}")
            logger.error(traceback.format_exc())
            return {'error': str(e)}, 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
