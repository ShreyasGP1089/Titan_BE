"""
Hybrid Search Pipeline
Integrates fine-tuned Qwen 3:4B with PostgreSQL + pgvector

Flow:
User → Qwen → Structured JSON → Keyword Filter → Semantic Ranking → Top Products → Qwen → Final Recommendations
"""
import logging
from typing import List, Dict, Optional, Union
from decimal import Decimal
from psycopg2.extras import RealDictCursor
from database import connect_db, release_connection
from embedding import get_embedding

logger = logging.getLogger(__name__)


def convert_decimals(obj):
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


def keyword_search(
    sport: str,
    category: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    price_limit: Optional[float] = None,
    experience_level: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Keyword-based product search with SQL filtering.
    
    Args:
        sport: Sport category (e.g., "Football", "Yoga")
        category: Product category (e.g., "Football Shoes", "Yoga Mat")
        keywords: List of search keywords (e.g., ["soccer", "cleats"])
        price_limit: Maximum price
        experience_level: User level (e.g., "beginner", "professional")
        limit: Maximum number of results
    
    Returns:
        List of product dictionaries (candidate products)
    
    Example:
        >>> keyword_search(
        ...     sport="Football",
        ...     category="Football Cleats",
        ...     keywords=["soccer", "cleats"],
        ...     price_limit=5000
        ... )
        [{"product_id": "...", "name": "...", ...}, ...]
    """
    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Build SQL query
        query = """
            SELECT 
                product_id,
                name,
                brand,
                price,
                mrp,
                sport,
                category_level_1,
                category_level_2,
                description,
                image_url,
                product_url,
                rating,
                review_count
            FROM products
            WHERE 1=1
        """
        params = []
        
        # Filter by sport
        if sport:
            query += " AND LOWER(sport) = LOWER(%s)"
            params.append(sport)
        
        # Filter by price
        if price_limit:
            query += " AND price <= %s"
            params.append(price_limit)
        
        # Keyword search across multiple fields
        if keywords and len(keywords) > 0:
            keyword_conditions = []
            for keyword in keywords:
                keyword_lower = f"%{keyword.lower()}%"
                keyword_conditions.append(
                    "(LOWER(name) LIKE %s OR LOWER(description) LIKE %s OR "
                    "LOWER(category_level_1) LIKE %s OR LOWER(category_level_2) LIKE %s)"
                )
                params.extend([keyword_lower] * 4)
            
            query += " AND (" + " OR ".join(keyword_conditions) + ")"
        
        # Filter by category if provided
        if category:
            category_lower = f"%{category.lower()}%"
            query += """ AND (
                LOWER(category_level_1) LIKE %s OR 
                LOWER(category_level_2) LIKE %s OR
                LOWER(name) LIKE %s
            )"""
            params.extend([category_lower] * 3)
        
        # Filter by experience level (in description or name)
        if experience_level:
            level_lower = f"%{experience_level.lower()}%"
            query += " AND (LOWER(description) LIKE %s OR LOWER(name) LIKE %s)"
            params.extend([level_lower] * 2)
        
        # Order by rating and limit
        query += " ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST"
        query += f" LIMIT {limit}"
        
        logger.info(f"Keyword search: sport={sport}, category={category}, keywords={keywords}, price_limit={price_limit}")
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        logger.info(f"Keyword search returned {len(results)} candidates")
        
        # Convert Decimals to float for JSON serialization
        return [convert_decimals(dict(row)) for row in results]
        
    except Exception as e:
        logger.error(f"Keyword search error: {e}")
        return []
    finally:
        cur.close()
        release_connection(conn)


def semantic_rank(
    query_text: str,
    candidate_products: List[Dict],
    top_k: int = 10
) -> List[Dict]:
    """
    Rank candidate products using semantic similarity.
    
    Args:
        query_text: Text query (e.g., "Football Cleats soccer cleats beginner")
        candidate_products: List of products from keyword_search
        top_k: Number of top results to return
    
    Returns:
        List of top-k products with similarity scores
    
    Example:
        >>> semantic_rank(
        ...     query_text="Football Cleats soccer cleats",
        ...     candidate_products=[...],
        ...     top_k=10
        ... )
        [{"product_id": "...", "similarity": 0.92, ...}, ...]
    """
    if not candidate_products:
        return []
    
    conn = connect_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Generate query embedding
        logger.info(f"Generating embedding for query: {query_text}")
        query_embedding = get_embedding(query_text)
        
        # Extract product IDs
        product_ids = [p['product_id'] for p in candidate_products]
        
        # Query with semantic similarity
        query = """
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
                1 - (pe.embedding <=> %s::vector) AS similarity
            FROM products p
            JOIN product_embeddings pe ON p.product_id = pe.product_id
            WHERE p.product_id = ANY(%s)
            ORDER BY pe.embedding <=> %s::vector
            LIMIT %s
        """
        
        cur.execute(query, (query_embedding, product_ids, query_embedding, top_k))
        results = cur.fetchall()
        
        logger.info(f"Semantic ranking returned {len(results)} products")
        
        # Convert Decimals to float for JSON serialization
        return [convert_decimals(dict(row)) for row in results]
        
    except Exception as e:
        logger.error(f"Semantic ranking error: {e}")
        # Fallback: return top-k from candidates based on rating
        sorted_candidates = sorted(
            candidate_products,
            key=lambda x: (x.get('rating') or 0, x.get('review_count') or 0),
            reverse=True
        )
        return sorted_candidates[:top_k]
    finally:
        cur.close()
        release_connection(conn)


def hybrid_search(
    sport: str,
    category: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    price_limit: Optional[float] = None,
    experience_level: Optional[str] = None,
    top_k: int = 10
) -> List[Dict]:
    """
    Hybrid search: Keyword filtering + Semantic ranking.
    
    Args:
        sport: Sport category
        category: Product category
        keywords: Search keywords
        price_limit: Maximum price
        experience_level: User skill level
        top_k: Number of final results
    
    Returns:
        List of top-k products with similarity scores
    
    Flow:
        1. Keyword search → Get 50-100 candidates
        2. If no candidates → Fallback to semantic search on entire sport
        3. Semantic ranking → Rank candidates by similarity
        4. Return top-k
    
    Example:
        >>> hybrid_search(
        ...     sport="Football",
        ...     category="Football Shoes",
        ...     keywords=["soccer", "cleats"],
        ...     price_limit=5000,
        ...     top_k=10
        ... )
        [{"product_id": "...", "name": "...", "similarity": 0.92, ...}, ...]
    """
    logger.info(f"Hybrid search: sport={sport}, category={category}, keywords={keywords}")
    
    # Step 1: Keyword search
    candidates = keyword_search(
        sport=sport,
        category=category,
        keywords=keywords,
        price_limit=price_limit,
        experience_level=experience_level,
        limit=100
    )
    
    # Step 2: Fallback if no candidates
    if not candidates:
        logger.warning(f"No candidates found, falling back to sport-wide semantic search")
        candidates = keyword_search(
            sport=sport,
            price_limit=price_limit,
            limit=100
        )
    
    if not candidates:
        logger.warning(f"No products found for sport={sport}")
        return []
    
    # Step 3: Build semantic query text
    query_parts = []
    if category:
        query_parts.append(category)
    if keywords:
        query_parts.extend(keywords)
    if experience_level:
        query_parts.append(experience_level)
    
    query_text = " ".join(query_parts) if query_parts else sport
    
    # Step 4: Semantic ranking
    ranked_products = semantic_rank(
        query_text=query_text,
        candidate_products=candidates,
        top_k=top_k
    )
    
    return ranked_products


def search_task(search_requests: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Execute multiple searches for task-based queries.
    
    Args:
        search_requests: List of search requests
            Example: [
                {"sport": "Camping", "category": "Tent", "keywords": []},
                {"sport": "Camping", "category": "Sleeping Bag", "keywords": []}
            ]
    
    Returns:
        Dictionary mapping categories to products
            Example: {
                "Tent": [{...}, {...}],
                "Sleeping Bag": [{...}, {...}]
            }
    
    Example:
        >>> search_task([
        ...     {"sport": "Camping", "category": "Tent", "keywords": []},
        ...     {"sport": "Camping", "category": "Sleeping Bag", "keywords": []}
        ... ])
        {
            "Tent": [{"product_id": "...", ...}, ...],
            "Sleeping Bag": [{"product_id": "...", ...}, ...]
        }
    """
    results = {}
    
    for req in search_requests:
        sport = req.get('sport')
        category = req.get('category')
        keywords = req.get('keywords', [])
        price_limit = req.get('price_limit')
        experience_level = req.get('experience_level')
        
        logger.info(f"Executing search: sport={sport}, category={category}")
        
        products = hybrid_search(
            sport=sport,
            category=category,
            keywords=keywords,
            price_limit=price_limit,
            experience_level=experience_level,
            top_k=5  # Fewer products per category for task queries
        )
        
        # Use category as key, fallback to sport
        key = category if category else sport
        results[key] = products
    
    return results


def format_products_for_llm(products: List[Dict], max_products: int = 10) -> str:
    """
    Format products for Qwen re-ranking and recommendation.
    
    Args:
        products: List of product dictionaries
        max_products: Maximum number of products to format
    
    Returns:
        Formatted string for LLM
    
    Example:
        >>> format_products_for_llm(products)
        '''
        1. Quechua MH100 Tent
           Brand: QUECHUA
           Price: ₹4999
           Rating: 4.5 ⭐ (234 reviews)
           Description: Family camping tent for beginners.
           Similarity: 0.92
           --------------------------------
        
        2. Quechua MH500 Tent
           Brand: QUECHUA
           Price: ₹6999
           Rating: 4.7 ⭐ (156 reviews)
           Description: Lightweight waterproof tent.
           Similarity: 0.90
           --------------------------------
        '''
    """
    if not products:
        return "No products found."
    
    formatted = []
    
    for i, product in enumerate(products[:max_products], 1):
        product_text = f"{i}. {product['name']}\n"
        product_text += f"   Brand: {product.get('brand', 'N/A')}\n"
        product_text += f"   Price: ₹{product['price']}\n"
        
        if product.get('rating'):
            rating = product['rating']
            review_count = product.get('review_count', 0)
            product_text += f"   Rating: {rating} ⭐"
            if review_count:
                product_text += f" ({review_count} reviews)"
            product_text += "\n"
        
        if product.get('description'):
            desc = product['description'][:150]  # Truncate long descriptions
            if len(product['description']) > 150:
                desc += "..."
            product_text += f"   Description: {desc}\n"
        
        if product.get('similarity'):
            similarity = round(product['similarity'], 2)
            product_text += f"   Similarity: {similarity}\n"
        
        product_text += "   " + "-" * 40
        formatted.append(product_text)
    
    return "\n\n".join(formatted)


def format_task_products_for_llm(task_results: Dict[str, List[Dict]]) -> str:
    """
    Format task-based search results for LLM.
    
    Args:
        task_results: Dictionary mapping categories to products
    
    Returns:
        Formatted string for LLM
    
    Example:
        >>> format_task_products_for_llm({
        ...     "Tent": [{...}, {...}],
        ...     "Sleeping Bag": [{...}, {...}]
        ... })
        '''
        === Tent ===
        
        1. Quechua MH100 Tent
           Brand: QUECHUA
           Price: ₹4999
           ...
        
        === Sleeping Bag ===
        
        1. Forclaz MT500 Sleeping Bag
           Brand: FORCLAZ
           Price: ₹3999
           ...
        '''
    """
    if not task_results:
        return "No products found."
    
    sections = []
    
    for category, products in task_results.items():
        section = f"=== {category} ===\n\n"
        section += format_products_for_llm(products, max_products=5)
        sections.append(section)
    
    return "\n\n".join(sections)


# Test function
def test_search_pipeline():
    """Test the search pipeline with example queries."""
    
    print("="*80)
    print("Testing Hybrid Search Pipeline")
    print("="*80)
    
    # Test 1: Simple search
    print("\n📝 Test 1: Football boots below 5000")
    results = hybrid_search(
        sport="Football",
        category="Football Shoes",
        keywords=["boots"],
        price_limit=5000,
        top_k=5
    )
    print(f"✓ Found {len(results)} products")
    if results:
        print(f"  Top product: {results[0]['name']} (₹{results[0]['price']}, similarity: {results[0].get('similarity', 'N/A')})")
    
    # Test 2: Task-based search
    print("\n📝 Test 2: Camping equipment")
    task_results = search_task([
        {"sport": "Camping", "category": "Tent", "keywords": []},
        {"sport": "Camping", "category": "Sleeping Bag", "keywords": []}
    ])
    print(f"✓ Found {len(task_results)} categories")
    for category, products in task_results.items():
        print(f"  {category}: {len(products)} products")
    
    # Test 3: Format for LLM
    print("\n📝 Test 3: Format products for LLM")
    if results:
        formatted = format_products_for_llm(results[:3])
        print("✓ Formatted output:")
        print(formatted[:300] + "...")
    
    print("\n" + "="*80)
    print("✅ Search pipeline tests complete!")
    print("="*80)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_search_pipeline()
