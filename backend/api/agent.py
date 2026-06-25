"""
Unified Agent Endpoint
Routes structured JSON requests to appropriate tools
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from flask_cors import CORS
from functools import wraps
from pydantic import ValidationError

from models.schemas import (
    SearchIntent,
    TaskIntent,
    CompareIntent,
    AlternativesIntent,
    SearchResponse,
    TaskResponse,
    CompareResponse,
    AlternativesResponse,
    ErrorResponse
)
from tools import SearchTool, TaskTool, CompareTool, AlternativesTool
from database import initialize_pool, close_pool
import atexit

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)

# API configuration
api = Api(
    app,
    version='2.0.0',
    title='Decathlon Agent API',
    description='''
    Pure Tool Execution API (No LLM, No Conversation)
    
    Architecture:
        User → Workflow Agent → SLM → Structured JSON → THIS API → PostgreSQL
    
    Supported Intents:
        - search: Product search with filters
        - task: Activity-based shopping (e.g., "Start Golf")
        - compare: Product comparison by IDs
        - alternatives: Find similar products
    ''',
    doc='/docs',
    prefix='/api/v1'
)

# API Key authentication
API_KEY = os.getenv('API_KEY', 'decathlon_agent_api_key_2024')


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


# Initialize database
_initialized = False


def initialize():
    """Initialize application resources"""
    global _initialized
    
    if _initialized:
        return
    
    logger.info("=" * 80)
    logger.info("INITIALIZING AGENT API")
    logger.info("=" * 80)
    
    try:
        # Initialize database pool
        logger.info("Initializing PostgreSQL connection pool...")
        initialize_pool(minconn=2, maxconn=20)
        logger.info("✓ PostgreSQL pool ready")
        
        _initialized = True
        
        logger.info("=" * 80)
        logger.info("✅ AGENT API READY")
        logger.info("=" * 80)
        logger.info("Architecture: Pure Tool Executor (No LLM)")
        logger.info("Supported Intents: search, task, compare, alternatives")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise


atexit.register(close_pool)

# Initialize tools
search_tool = SearchTool()
task_tool = TaskTool()
compare_tool = CompareTool()
alternatives_tool = AlternativesTool()

# Namespace
ns = api.namespace('agent', description='Unified agent endpoint')

# Request models (for Swagger UI)
search_request_model = api.model('SearchRequest', {
    'sport': fields.String(required=True, description='Sport category', example='Hiking'),
    'category_level_1': fields.String(description='Level 1 category', example='Footwear'),
    'category_level_2': fields.String(description='Level 2 category', example='Hiking Shoes'),
    'keywords': fields.List(fields.String, description='Search keywords', example=['waterproof', 'shoes']),
    'price_limit': fields.Float(description='Maximum price', example=6000)
})

search_intent_model = api.model('SearchIntent', {
    'intent': fields.String(required=True, enum=['search'], example='search'),
    'search_request': fields.Nested(search_request_model, required=True)
})

task_arguments_model = api.model('TaskArguments', {
    'activity': fields.String(required=True, description='Activity name', example='Golf'),
    'budget': fields.Float(description='Total budget', example=15000)
})

task_intent_model = api.model('TaskIntent', {
    'intent': fields.String(required=True, enum=['task'], example='task'),
    'arguments': fields.Nested(task_arguments_model, required=True)
})

compare_arguments_model = api.model('CompareArguments', {
    'products': fields.List(fields.String, required=True, min_items=2, description='Product IDs', example=['MH500', 'NH500'])
})

compare_intent_model = api.model('CompareIntent', {
    'intent': fields.String(required=True, enum=['compare'], example='compare'),
    'arguments': fields.Nested(compare_arguments_model, required=True)
})

alternatives_arguments_model = api.model('AlternativesArguments', {
    'product': fields.String(required=True, description='Product ID to find alternatives for', example='MH500')
})

alternatives_intent_model = api.model('AlternativesIntent', {
    'intent': fields.String(required=True, enum=['alternatives'], example='alternatives'),
    'arguments': fields.Nested(alternatives_arguments_model, required=True)
})


@ns.route('')
class AgentEndpoint(Resource):
    """Unified agent endpoint"""
    
    @api.doc('agent_execute')
    @api.expect(search_intent_model, validate=False)  # Accept any of the intent models
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(401, 'Unauthorized')
    @api.response(500, 'Internal Server Error')
    @require_api_key
    def post(self):
        """
        Execute agent request (search, task, or compare)
        
        This endpoint receives structured JSON from the Workflow Agent
        and routes to the appropriate tool.
        
        Examples:
        
        1. Search Intent:
        {
            "intent": "search",
            "search_request": {
                "sport": "Hiking",
                "category_level_1": "Footwear",
                "keywords": ["waterproof", "shoes"],
                "price_limit": 6000
            }
        }
        
        2. Task Intent:
        {
            "intent": "task",
            "arguments": {
                "activity": "Golf",
                "budget": 15000
            }
        }
        
        3. Compare Intent:
        {
            "intent": "compare",
            "arguments": {
                "products": ["MH500", "NH500"]
            }
        }
        
        4. Alternatives Intent:
        {
            "intent": "alternatives",
            "arguments": {
                "product": "MH500"
            }
        }
        """
        # Ensure initialization
        initialize()
        
        try:
            data = request.get_json()
            
            if not data:
                return {'error': 'Bad Request', 'message': 'JSON body required'}, 400
            
            intent = data.get('intent')
            
            if not intent:
                return {'error': 'Bad Request', 'message': 'intent field required'}, 400
            
            logger.info(f"Processing intent: {intent}")
            
            # Route to appropriate tool
            if intent == 'search':
                # Validate and execute search
                try:
                    search_intent = SearchIntent(**data)
                    response = search_tool.execute(search_intent.search_request)
                    return response.dict(), 200
                except ValidationError as e:
                    logger.error(f"Validation error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
            
            elif intent == 'task':
                # Validate and execute task
                try:
                    task_intent = TaskIntent(**data)
                    response = task_tool.execute(task_intent.arguments)
                    return response.dict(), 200
                except ValidationError as e:
                    logger.error(f"Validation error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
                except ValueError as e:
                    logger.error(f"Task error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
            
            elif intent == 'compare':
                # Validate and execute compare
                try:
                    compare_intent = CompareIntent(**data)
                    response = compare_tool.execute(compare_intent.arguments)
                    return response.dict(), 200
                except ValidationError as e:
                    logger.error(f"Validation error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
                except ValueError as e:
                    logger.error(f"Compare error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
            
            elif intent == 'alternatives':
                # Validate and execute alternatives
                try:
                    alternatives_intent = AlternativesIntent(**data)
                    response = alternatives_tool.execute(alternatives_intent.arguments)
                    return response.dict(), 200
                except ValidationError as e:
                    logger.error(f"Validation error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
                except ValueError as e:
                    logger.error(f"Alternatives error: {e}")
                    return {'error': 'Bad Request', 'message': str(e)}, 400
            
            else:
                return {
                    'error': 'Bad Request',
                    'message': f'Unknown intent: {intent}. Supported: search, task, compare, alternatives'
                }, 400
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                'error': 'Internal Server Error',
                'message': str(e)
            }, 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'api': 'Agent API',
        'version': '2.0.0',
        'architecture': 'Pure Tool Executor (No LLM)',
        'supported_intents': ['search', 'task', 'compare', 'alternatives']
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting Agent API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
