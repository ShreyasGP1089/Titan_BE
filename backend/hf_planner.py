"""
Shopping Planner with Local Model Client
Uses HTTP to call local model server running on Mac

Flow:
User Query → Local Model (via HTTP) → Structured JSON → Hybrid Search → Products → Local Model → Recommendations
"""
import json
import logging
import os
import re
from typing import Dict, List, Optional
from local_model_client import get_client

from search_pipeline import (
    hybrid_search,
    search_task,
    format_products_for_llm,
    format_task_products_for_llm
)

logger = logging.getLogger(__name__)


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON syntax errors from LLM output.
    
    Args:
        json_str: Potentially malformed JSON string
    
    Returns:
        Repaired JSON string
    """
    repaired = json_str
    
    # Fix 1: Extract price_limit if it's inside keywords array
    price_limit_match = re.search(r'"keywords"\s*:\s*\[(.*?)"price_limit"\s*:\s*(\d+)', repaired, re.DOTALL)
    extracted_price = None
    if price_limit_match:
        extracted_price = price_limit_match.group(2)
        logger.info(f"Found price_limit={extracted_price} inside keywords array, will relocate it")
    
    # Fix 2: Trailing comma before closing bracket/brace
    repaired = re.sub(r',\s*]', ']', repaired)
    repaired = re.sub(r',\s*}', '}', repaired)
    
    # Fix 3: Missing comma between array close and next field
    repaired = re.sub(r']\s*"', '],"', repaired)
    repaired = re.sub(r'}\s*"', '},"', repaired)
    
    # Fix 4: Remove malformed items in arrays
    def clean_array(match):
        array_content = match.group(1)
        items = re.findall(r'"([^"]+)"(?=\s*[,\]])', array_content)
        return '[' + ','.join(f'"{item}"' for item in items if ':' not in item) + ']'
    
    repaired = re.sub(r'\[([^\]]+)\]', clean_array, repaired)
    
    # Fix 5: Add back extracted price_limit
    if extracted_price:
        repaired = re.sub(
            r'("keywords"\s*:\s*\[[^\]]*\])',
            r'\1,\n    "price_limit": ' + extracted_price,
            repaired
        )
        logger.info(f"Relocated price_limit={extracted_price} to correct position")
    
    return repaired


def parse_query_with_local_model(user_query: str) -> Optional[Dict]:
    """
    Parse user query into structured JSON using local model server.
    
    Args:
        user_query: Natural language query
    
    Returns:
        Structured JSON dict or None if parsing fails
    """
    try:
        logger.info("Calling local model server for query parsing...")
        
        client = get_client()
        
        logger.info(f"Parsing query with local model: {user_query}")
        logger.info("⏳ Generating response (this may take 20-40 seconds)...")
        
        # Call local model server's /parse-query endpoint
        # This returns parsed JSON directly, no string parsing needed!
        parsed_query = client.parse_query(user_query)
        
        logger.info("✓ Response received")
        logger.info(f"✓ Successfully parsed: intent={parsed_query.get('intent')}")
        
        return parsed_query
        
    except Exception as e:
        logger.error(f"Query parsing error: {e}", exc_info=True)
        return None


# Alias for backwards compatibility
parse_query_with_qwen = parse_query_with_local_model


def execute_search(parsed_query: Dict) -> Dict:
    """
    Execute search based on parsed query.
    
    Args:
        parsed_query: Structured query from Qwen
    
    Returns:
        Search results dictionary
    """
    intent = parsed_query.get('intent')
    
    if intent == 'search':
        # Single search request
        search_req = parsed_query.get('search_request', {})
        
        results = hybrid_search(
            sport=search_req.get('sport'),
            category=search_req.get('category'),
            keywords=search_req.get('keywords', []),
            price_limit=search_req.get('price_limit'),
            experience_level=search_req.get('experience_level'),
            top_k=10
        )
        
        return {
            'intent': 'search',
            'products': results,
            'formatted': format_products_for_llm(results)
        }
        
    elif intent == 'task':
        # Multiple search requests
        search_requests = parsed_query.get('search_requests', [])
        
        task_results = search_task(search_requests)
        
        return {
            'intent': 'task',
            'products_by_category': task_results,
            'formatted': format_task_products_for_llm(task_results)
        }
    
    else:
        logger.warning(f"Unknown intent: {intent}")
        return {'intent': 'unknown', 'products': [], 'formatted': 'No products found.'}


def generate_recommendations(
    user_query: str,
    parsed_query: Dict,
    search_results: Dict
) -> str:
    """
    Generate final recommendations using local model server.
    
    Args:
        user_query: Original user query
        parsed_query: Structured query
        search_results: Products from hybrid search
    
    Returns:
        Natural language recommendations
    """
    try:
        client = get_client()
        
        # Build recommendation prompt
        prompt = f"""You are a helpful shopping assistant for Decathlon. Based on the user's query and the following products, provide personalized recommendations.

User Query: {user_query}

Products Found:
{search_results['formatted']}

Provide a helpful response that:
1. Acknowledges the user's needs
2. Recommends the top 3-5 products with reasons
3. Mentions key features (price, rating, brand)
4. Is friendly and concise"""
        
        logger.info("Generating recommendations with local model")
        
        response = client.generate(prompt, max_new_tokens=512)
        
        logger.info("✓ Recommendations generated")
        return response
        
    except Exception as e:
        logger.error(f"Recommendation generation error: {e}")
        # Fallback: Simple recommendation
        if search_results.get('products'):
            top_product = search_results['products'][0]
            return (
                f"I found some great options for you! "
                f"I'd recommend the {top_product['name']} "
                f"by {top_product.get('brand', 'Decathlon')} "
                f"priced at ₹{top_product['price']}."
            )
        return "I couldn't find any products matching your criteria. Please try a different search."


def shopping_planner_hf(user_query: str) -> Dict:
    """
    Complete shopping planner pipeline with local model server.
    
    Flow:
        1. Parse query with local model → Structured JSON
        2. Execute hybrid search → Products
        3. Generate recommendations with local model → Natural language
    
    Args:
        user_query: Natural language user query
    
    Returns:
        Complete response dictionary
    """
    logger.info(f"Processing query: {user_query}")
    
    try:
        # Step 1: Parse query with local model
        parsed_query = parse_query_with_local_model(user_query)
        
        if not parsed_query:
            return {
                'status': 'error',
                'error': 'Failed to parse query',
                'user_query': user_query
            }
        
        # Step 2: Execute search
        search_results = execute_search(parsed_query)
        
        # Step 3: Generate recommendations
        recommendations = generate_recommendations(
            user_query=user_query,
            parsed_query=parsed_query,
            search_results=search_results
        )
        
        # Build response
        response = {
            'status': 'success',
            'user_query': user_query,
            'parsed_query': parsed_query,
            'intent': parsed_query.get('intent'),
            'recommendations': recommendations,
            'metadata': {
                'model': 'Qwen2.5-1.5B-Instruct (Local Server)',
                'search_type': 'hybrid',
                'products_found': len(search_results.get('products', []))
            }
        }
        
        # Add products based on intent
        if parsed_query.get('intent') == 'search':
            response['products'] = search_results.get('products', [])
        elif parsed_query.get('intent') == 'task':
            response['products_by_category'] = search_results.get('products_by_category', {})
        
        logger.info(f"✓ Query processed successfully: {response['metadata']['products_found']} products found")
        
        return response
        
    except Exception as e:
        logger.error(f"Shopping planner error: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'user_query': user_query
        }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test
    print("Testing Hugging Face planner...")
    result = shopping_planner_hf("running shoes under 5000")
    print(json.dumps(result, indent=2))
