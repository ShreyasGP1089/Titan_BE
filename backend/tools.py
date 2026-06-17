"""
Tool functions for the AI shopping planner.
These tools interact with PostgreSQL and provide data to the LLM.
"""
import logging
from typing import List, Dict, Optional
from db import execute_query
from embedding import get_embedding
from config import DEFAULT_SEARCH_LIMIT

logger = logging.getLogger(__name__)


def hybrid_search(
    query: str,
    sport: Optional[str] = None,
    price_limit: Optional[float] = None,
    limit: int = DEFAULT_SEARCH_LIMIT
) -> List[Dict]:
    """
    Perform hybrid search using vector similarity and SQL filters.
    
    Args:
        query: Search query text
        sport: Filter by sport category (optional)
        price_limit: Maximum price filter (optional)
        limit: Number of results to return (default 10)
    
    Returns:
        List of product dictionaries with metadata
    """
    try:
        logger.info(f"Hybrid search: query='{query}', sport={sport}, price_limit={price_limit}, limit={limit}")
        
        # Generate query embedding
        query_embedding = get_embedding(query)
        
        # Build SQL query with filters
        sql = """
        SELECT 
            p.product_id,
            p.name,
            p.brand,
            p.price,
            p.mrp,
            p.sport,
            p.category_level_1,
            p.category_level_2,
            p.description,
            p.image_url,
            p.product_url,
            p.rating,
            p.review_count,
            1 - (pe.embedding <=> %s::vector) AS similarity_score
        FROM products p
        JOIN product_embeddings pe ON p.product_id = pe.product_id
        WHERE 
            (%s IS NULL OR LOWER(p.sport) = LOWER(%s))
            AND (%s IS NULL OR p.price <= %s)
            AND p.price IS NOT NULL
        ORDER BY pe.embedding <=> %s::vector
        LIMIT %s;
        """
        
        params = (
            query_embedding,  # for similarity score calculation
            sport, sport,  # sport filter (check NULL and value)
            price_limit, price_limit,  # price filter
            query_embedding,  # for ordering
            limit
        )
        
        results = execute_query(sql, params, fetch=True)
        
        logger.info(f"Found {len(results)} products")
        return results
        
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []


def get_categories() -> List[Dict]:
    """
    Get all distinct sports and categories from the database.
    
    Returns:
        List of dictionaries with sport and category information
    """
    try:
        logger.info("Fetching categories")
        
        sql = """
        SELECT DISTINCT
            sport,
            category_level_1,
            category_level_2
        FROM products
        WHERE sport IS NOT NULL
        ORDER BY sport, category_level_1, category_level_2;
        """
        
        results = execute_query(sql, fetch=True)
        
        logger.info(f"Found {len(results)} unique category combinations")
        return results
        
    except Exception as e:
        logger.error(f"Failed to fetch categories: {e}")
        return []


def compare_products(product_ids: List[str]) -> List[Dict]:
    """
    Get detailed information for specific products by IDs.
    
    Args:
        product_ids: List of product IDs to compare
    
    Returns:
        List of product dictionaries with full metadata
    """
    try:
        logger.info(f"Comparing products: {product_ids}")
        
        if not product_ids:
            return []
        
        # Build query with parameterized IN clause
        placeholders = ','.join(['%s'] * len(product_ids))
        sql = f"""
        SELECT 
            p.product_id,
            p.name,
            p.brand,
            p.price,
            p.mrp,
            p.sport,
            p.category_level_1,
            p.category_level_2,
            p.description,
            p.image_url,
            p.product_url,
            p.rating,
            p.review_count
        FROM products p
        WHERE p.product_id IN ({placeholders})
        ORDER BY p.rating DESC NULLS LAST, p.review_count DESC NULLS LAST;
        """
        
        results = execute_query(sql, tuple(product_ids), fetch=True)
        
        logger.info(f"Found {len(results)} products for comparison")
        return results
        
    except Exception as e:
        logger.error(f"Product comparison failed: {e}")
        return []


def get_product_by_id(product_id: str) -> Optional[Dict]:
    """
    Get a single product by ID.
    
    Args:
        product_id: Product ID
    
    Returns:
        Product dictionary or None if not found
    """
    try:
        sql = """
        SELECT 
            p.product_id,
            p.name,
            p.brand,
            p.price,
            p.mrp,
            p.sport,
            p.category_level_1,
            p.category_level_2,
            p.description,
            p.image_url,
            p.product_url,
            p.rating,
            p.review_count
        FROM products p
        WHERE p.product_id = %s;
        """
        
        results = execute_query(sql, (product_id,), fetch=True)
        return results[0] if results else None
        
    except Exception as e:
        logger.error(f"Failed to fetch product {product_id}: {e}")
        return None
