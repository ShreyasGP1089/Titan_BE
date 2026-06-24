"""
Hybrid Search Service
TRUE Hybrid Search: Combines keyword matching scores with semantic similarity

Scoring Formula:
    final_score = (semantic_score * 0.6) + (keyword_score * 0.4)

Keyword Scoring Priority:
    - Description Match: 1.0 (highest priority)
    - Product Name Match: 0.8
    - Exact Match Boost: +0.2
    - All Keywords Match Bonus: +0.3

This prevents accessories/apparel from ranking above actual equipment.
"""
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from psycopg2.extras import RealDictCursor
from database import connect_db, release_connection
from services.embedding_service import EmbeddingService

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


class HybridSearchService:
    """
    True Hybrid Search Service
    
    Combines:
    1. Keyword Scoring (name, description matching with word-boundary regex)
    2. Semantic Scoring (vector similarity)
    
    Final Score = 0.6 * semantic + 0.4 * keyword
    """
    
    # Scoring weights
    SEMANTIC_WEIGHT = 0.6
    KEYWORD_WEIGHT = 0.4
    
    # Keyword match weights
    NAME_MATCH_SCORE = 1.0      # Highest priority
    DESCRIPTION_MATCH_SCORE = 0.3  # Lowest priority
    EXACT_MATCH_BOOST = 0.2     # Bonus for exact word match
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
    
    def _safe_lower(self, value) -> str:
        """
        Safely convert a value to lowercase string.
        
        Handles None, non-string types, and missing values.
        
        Args:
            value: Any value (str, None, int, etc.)
        
        Returns:
            Lowercase string, empty string if None/invalid
        """
        if value is None:
            return ''
        if not isinstance(value, str):
            return str(value).lower() if value else ''
        return value.lower()
    
    def calculate_keyword_score(
        self,
        product: Dict,
        keywords: List[str]
    ) -> float:
        """
        Calculate keyword match score for a product.
        
        Scoring:
        - Product name contains keyword: 1.0 (Highest priority)
        - Exact match in product name: +0.2 boost
        - Description contains keyword: 0.3 (Lowest priority)
        
        For multi-keyword search, computes the maximum score among keywords,
        plus a small bonus for matching multiple keywords. This prevents 
        diluting scores of perfect matches for alternative keywords (e.g. Golf clubs).
        
        NULL-SAFE: Handles None values in all product fields.
        
        Returns score in range [0.0, 1.5]
        """
        if not keywords:
            return 0.5  # Neutral score if no keywords
        
        # NULL-SAFE: Use _safe_lower to handle None
        product_name = self._safe_lower(product.get('name'))
        description = self._safe_lower(product.get('description'))
        cat1_lower = self._safe_lower(product.get('category_level_1'))
        
        # Stemming variations (singular/plural)
        def get_variations(word: str) -> List[str]:
            w = word.lower()
            vars = [w]
            if w.endswith('s') and len(w) > 3:
                vars.append(w[:-1])
                if w.endswith('es') and len(w) > 4:
                    vars.append(w[:-2])
            else:
                vars.append(w + 's')
                vars.append(w + 'es')
            return list(set(vars))
        
        individual_scores = []
        unique_matches = 0
        
        for keyword in keywords:
            vars = get_variations(keyword)
            keyword_score = 0.0
            matched = False
            
            # Check description (low priority)
            if any(var in description for var in vars):
                keyword_score = self.DESCRIPTION_MATCH_SCORE
                matched = True
            
            # Check product name (highest priority)
            if any(var in product_name for var in vars):
                words = product_name.split()
                # Find matching variation in product name words
                matching_vars_in_words = [var for var in vars if var in words]
                matching_vars_anywhere = [var for var in vars if any(var in word for word in words)]
                
                if matching_vars_anywhere:
                    name_score = self.NAME_MATCH_SCORE
                    
                    # Bonus for exact word match
                    if matching_vars_in_words:
                        name_score += self.EXACT_MATCH_BOOST
                    
                    # Use higher of name or description score
                    if name_score > keyword_score:
                        keyword_score = name_score
                    
                    matched = True
            
            if matched:
                unique_matches += 1
            individual_scores.append(keyword_score)
        
        base_score = max(individual_scores) if individual_scores else 0.0
        
        # Add a bonus of 0.1 for every other keyword matched beyond the first one
        additional_match_bonus = 0.1 * (unique_matches - 1) if unique_matches > 1 else 0.0
        
        # Multi-keyword match bonus: reward products matching ALL keywords
        match_ratio = unique_matches / len(keywords) if len(keywords) > 0 else 0.0
        all_match_bonus = 0.3 if match_ratio == 1.0 else 0.0
        
        # Core equipment category boost (e.g. prioritize clubs/balls over accessories/apparel)
        equipment_boost = 0.0
        is_equipment = any(
            eq_word in cat1_lower 
            for eq_word in ['equipment', 'balls', 'bicycles', 'camping gear', 'footwear', 'safety equipment']
        )
        if is_equipment and base_score > 0:
            equipment_boost = 0.15
            
        return min(base_score + additional_match_bonus + all_match_bonus + equipment_boost, 1.5)
    
    def keyword_filter(
        self,
        sport: str,
        category_level_1: Optional[str] = None,
        category_level_2: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        price_limit: Optional[float] = None,
        limit: int = 100,
        keyword_mode: str = 'AND'
    ) -> List[Dict]:
        """
        Keyword-based product filtering using SQL.
        
        Strategy:
            sport + category_level_1 + category_level_2 + price_limit (AND)
            keywords match name OR description (AND or OR based on keyword_mode)
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
            
            # Filter by sport (required)
            query += " AND LOWER(sport) = LOWER(%s)"
            params.append(sport)
            
            # Filter by category_level_1
            if category_level_1:
                query += " AND LOWER(category_level_1) = LOWER(%s)"
                params.append(category_level_1)
            
            # Filter by category_level_2
            if category_level_2:
                query += " AND LOWER(category_level_2) = LOWER(%s)"
                params.append(category_level_2)
            
            # Filter by price
            if price_limit:
                query += " AND price <= %s"
                params.append(price_limit)
            
            # Full-text search: precise word matching with stemming (name OR description)
            # plainto_tsquery safely handles any user input
            # Stemming: "clubs" matches "club", "running" matches "run"
            if keywords and len(keywords) > 0:
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append(
                        "to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '')) @@ plainto_tsquery('english', %s)"
                    )
                    params.append(keyword)
                
                # AND mode: product must contain ALL keywords; OR mode: any keyword
                joiner = " AND " if keyword_mode == 'AND' else " OR "
                query += " AND (" + joiner.join(keyword_conditions) + ")"
            
            # Order by rating and limit
            query += " ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST"
            query += f" LIMIT {limit}"
            
            logger.info(f"Keyword filter: sport={sport}, cat1={category_level_1}, cat2={category_level_2}, keywords={keywords}, price<={price_limit}, mode={keyword_mode}")
            
            cur.execute(query, params)
            results = cur.fetchall()
            
            logger.info(f"✓ Keyword filter returned {len(results)} candidates")
            
            return [convert_decimals(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Keyword filter error: {e}")
            return []
        finally:
            cur.close()
            release_connection(conn)
    
    def semantic_search(
        self,
        query_text: str,
        candidate_products: List[Dict]
    ) -> Dict[str, float]:
        """
        Get semantic similarity scores for candidates.
        
        Returns:
            Dict mapping product_id to semantic similarity score [0.0, 1.0]
        """
        if not candidate_products:
            return {}
        
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Generate query embedding
            logger.info(f"Generating embedding for: {query_text}")
            query_embedding = self.embedding_service.embed_text(query_text)
            
            # Extract product IDs
            product_ids = [p['product_id'] for p in candidate_products]
            
            # Query with semantic similarity
            query = """
                SELECT 
                    p.product_id,
                    1 - (pe.embedding <=> %s::vector) AS similarity
                FROM products p
                JOIN product_embeddings pe ON p.product_id = pe.product_id
                WHERE p.product_id = ANY(%s)
            """
            
            cur.execute(query, (query_embedding, product_ids))
            results = cur.fetchall()
            
            # Build product_id → similarity map
            similarity_map = {row['product_id']: float(row['similarity']) for row in results}
            
            logger.info(f"✓ Semantic search scored {len(similarity_map)} products")
            
            return similarity_map
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return {}
        finally:
            cur.close()
            release_connection(conn)
    
    def hybrid_rank(
        self,
        query_text: str,
        keywords: List[str],
        candidate_products: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """
        TRUE HYBRID RANKING: Combine keyword and semantic scores.
        
        Formula:
            final_score = (semantic_score * 0.6) + (keyword_score * 0.4)
        
        Args:
            query_text: Text for semantic embedding
            keywords: Keywords for keyword matching
            candidate_products: Products to rank
            top_k: Number of top results to return
        
        Returns:
            Ranked products with score breakdown
        """
        if not candidate_products:
            return []
        
        logger.info("=" * 80)
        logger.info("HYBRID RANKING")
        logger.info(f"Query: {query_text}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Candidates: {len(candidate_products)}")
        logger.info("=" * 80)
        
        # Get semantic scores
        semantic_scores = self.semantic_search(query_text, candidate_products)
        
        # Calculate keyword scores and combine
        ranked_products = []
        
        for product in candidate_products:
            product_id = product['product_id']
            product_name = product['name']
            
            # Get semantic score
            semantic_score = semantic_scores.get(product_id, 0.0)
            
            # Calculate keyword score
            keyword_score = self.calculate_keyword_score(product, keywords)
            
            # Calculate final hybrid score
            final_score = (semantic_score * self.SEMANTIC_WEIGHT) + (keyword_score * self.KEYWORD_WEIGHT)
            
            # Add scores to product
            product_with_scores = product.copy()
            product_with_scores['semantic_score'] = round(semantic_score, 4)
            product_with_scores['keyword_score'] = round(keyword_score, 4)
            product_with_scores['final_score'] = round(final_score, 4)
            
            ranked_products.append(product_with_scores)
        
        # Sort by final score (descending)
        ranked_products.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Log top results
        logger.info("TOP RANKED PRODUCTS:")
        for i, p in enumerate(ranked_products[:top_k], 1):
            logger.info(f"{i}. {p['name']}")
            logger.info(f"   Semantic: {p['semantic_score']:.3f}, Keyword: {p['keyword_score']:.3f}, Final: {p['final_score']:.3f}")
        logger.info("=" * 80)
        
        # Return top_k
        return ranked_products[:top_k]
    
    def search(
        self,
        sport: str,
        category_level_1: Optional[str] = None,
        category_level_2: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        price_limit: Optional[float] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """
        TRUE HYBRID SEARCH: keyword scoring + semantic scoring.
        
        Flow:
            1. Keyword filter → candidates (up to 100)
            2. Calculate keyword scores for each candidate
            3. Calculate semantic scores for each candidate
            4. Combine: final_score = 0.6*semantic + 0.4*keyword
            5. Return top_k by final score
        
        This prevents accessories (towels, apparel) from ranking above
        actual equipment (clubs, balls) when searching for equipment.
        """
        logger.info("=" * 80)
        logger.info("HYBRID SEARCH REQUEST")
        logger.info(f"Sport: {sport}")
        logger.info(f"Category L1: {category_level_1}")
        logger.info(f"Category L2: {category_level_2}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Price Limit: {price_limit}")
        logger.info("=" * 80)
        
        # Graduated fallback cascade for candidate retrieval
        candidates = []
        fallback_step = 0
        
        # Step 1: Strictest — sport + category + keywords (AND) + price
        if keywords and len(keywords) > 1:
            candidates = self.keyword_filter(
                sport=sport,
                category_level_1=category_level_1,
                category_level_2=category_level_2,
                keywords=keywords,
                price_limit=price_limit,
                limit=100,
                keyword_mode='AND'
            )
            fallback_step = 1
            if candidates:
                logger.info(f"✓ Step 1 (AND keywords + category): {len(candidates)} candidates")
        
        # Step 2: Relax keyword mode — sport + category + keywords (OR) + price
        if not candidates:
            candidates = self.keyword_filter(
                sport=sport,
                category_level_1=category_level_1,
                category_level_2=category_level_2,
                keywords=keywords,
                price_limit=price_limit,
                limit=100,
                keyword_mode='OR'
            )
            fallback_step = 2
            if candidates:
                logger.info(f"✓ Step 2 (OR keywords + category): {len(candidates)} candidates")
        
        # Step 3: Drop category — sport + keywords (OR) + price
        if not candidates and category_level_1:
            logger.warning("No category candidates, trying sport + keywords only")
            candidates = self.keyword_filter(
                sport=sport,
                keywords=keywords,
                price_limit=price_limit,
                limit=100,
                keyword_mode='OR'
            )
            fallback_step = 3
            if candidates:
                logger.info(f"✓ Step 3 (OR keywords, no category): {len(candidates)} candidates")
        
        # Step 4: Final fallback — sport + price only
        if not candidates:
            logger.warning("No keyword candidates, falling back to sport-only")
            candidates = self.keyword_filter(
                sport=sport,
                price_limit=price_limit,
                limit=100
            )
            fallback_step = 4
            if candidates:
                logger.info(f"✓ Step 4 (sport-only fallback): {len(candidates)} candidates")
        
        if not candidates:
            logger.warning(f"No products found for sport={sport}")
            return []
        
        logger.info(f"✓ Found {len(candidates)} candidates (fallback step {fallback_step})")
        
        # Build semantic query text — always include sport for full context
        query_parts = [sport]
        if category_level_1:
            query_parts.append(category_level_1)
        if category_level_2:
            query_parts.append(category_level_2)
        if keywords:
            query_parts.extend(keywords)
        
        query_text = " ".join(query_parts)
        
        # Hybrid ranking (keyword + semantic)
        ranked_products = self.hybrid_rank(
            query_text=query_text,
            keywords=keywords or [],
            candidate_products=candidates,
            top_k=top_k
        )
        
        logger.info(f"✓ Hybrid search returned {len(ranked_products)} products")
        
        return ranked_products
