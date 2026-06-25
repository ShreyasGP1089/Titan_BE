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
from services.validation_service import ProductValidationService

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
    
    KNOWN_PRODUCT_TYPES = {
        'glove', 'gloves', 'backpack', 'backpacks', 'bottle', 'bottles', 'tent', 'tents', 
        'football', 'footballs', 'helmet', 'helmets', 'racket', 'rackets', 'shoe', 'shoes', 
        'sock', 'socks', 'trouser', 'trousers', 'short', 'shorts', 'jacket', 'jackets', 
        'ball', 'balls', 'mat', 'mats', 'bag', 'bags', 'pole', 'poles', 'watch', 'watches', 
        'cap', 'caps', 'goggle', 'goggles', 'swimsuit', 'swimsuits', 'jersey', 'jerseys', 
        'shirt', 'shirts', 'guard', 'guards', 'block', 'blocks', 'strap', 'straps', 
        'chair', 'chairs', 'stove', 'stoves', 'lamp', 'lamps'
    }
    
    EXCLUDED_MODIFIERS = {
        'cover', 'covers', 'bag', 'bags', 'holder', 'holders', 'net', 'nets', 
        'pump', 'pumps', 'whistle', 'whistles', 'card', 'cards', 'armband', 'armbands', 
        'bib', 'bibs', 'ladder', 'ladders', 'warmer', 'warmers', 'tights', 'goal', 'goals', 
        'guard', 'guards', 'pads', 'pad', 'strap', 'straps', 'cleaning', 'brush', 'brushes',
        'jersey', 'jerseys', 'shirt', 'shirts', 'short', 'shorts', 'jacket', 'jackets',
        'socks', 'sock', 'trouser', 'trousers', 'cap', 'caps', 'goggle', 'goggles',
        'swimsuit', 'swimsuits', 'helmet', 'helmets', 'racket', 'rackets', 'cone', 'cones',
        'marker', 'markers', 'saucer', 'saucers', 'needle', 'needles', 'referee',
        'capacity', 'sleeve', 'sleeves'
    }
    
    BROAD_QUERY_MODIFIERS = {
        'gear', 'equipment', 'products', 'accessories', 'kit', 'kits'
    }
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.validation_service = ProductValidationService()
        
    def _get_product_type_variations(self, product_type: str) -> List[str]:
        w = product_type.lower()
        vars = [w]
        if w.endswith('s') and len(w) > 3:
            vars.append(w[:-1])
            if w.endswith('es') and len(w) > 4:
                vars.append(w[:-2])
        else:
            vars.append(w + 's')
            vars.append(w + 'es')
        return list(set(vars))
        
    def _matches_product_type(self, name: str, description: str, requested_types: List[str], category_level_1: str = '', category_level_2: str = '') -> bool:
        if not requested_types:
            return True
        name_lower = name.lower() if name else ""
        desc_lower = description.lower() if description else ""
        cat1_lower = category_level_1.lower() if category_level_1 else ""
        cat2_lower = category_level_2.lower() if category_level_2 else ""
        
        # 1. First check presence of the product type in name or matching category fields (not solely description)
        has_presence = False
        for p_type in requested_types:
            variations = self._get_product_type_variations(p_type)
            if any(var in name_lower or var in cat1_lower or var in cat2_lower for var in variations):
                has_presence = True
                break
                
        if not has_presence:
            return False
            
        # 2. Dynamic check for pre-modifier relation phrases:
        # e.g., "for [product_type]", "fits inside [product_type]", "compatible with [product_type]"
        for p_type in requested_types:
            variations = self._get_product_type_variations(p_type)
            for var in variations:
                for prefix in ['for ', 'fits inside ', 'fits in ', 'inside ', 'compatible with ', 'protection for ', 'to protect ', 'suitable for ', 'designed for ']:
                    if prefix + var in name_lower:
                        logger.info(f"Excluding '{name}' because it contains '{prefix + var}' (pre-modifier phrase relationship)")
                        return False

        # 3. Preposition/context-aware check for exclusion modifiers
        # If any word in name is an exclusion modifier, it must be preceded by an accessory-introducing word ('with', 'including', 'and', '+')
        name_words = [w.strip('.,()[]-+*#') for w in name_lower.split()]
        name_words = [w for w in name_words if w]
        
        active_exclusions = self.EXCLUDED_MODIFIERS.copy()
        for p_type in requested_types:
            variations = self._get_product_type_variations(p_type)
            for var in variations:
                active_exclusions.discard(var)
                
        # Backpack-specific: discard 'bag'/'bags' because "backpack bag" is a common valid name
        if any(pt in ['backpack', 'backpacks'] for pt in requested_types):
            active_exclusions.discard('bag')
            active_exclusions.discard('bags')
            
        # Excluded items that are allowed to be bundled as physical accessories
        ALLOW_ACCESSORIES = {
            'cover', 'covers', 'holder', 'holders', 'net', 'nets', 'whistle', 'whistles', 
            'card', 'cards', 'strap', 'straps', 'brush', 'brushes', 'needle', 'needles'
        }
                
        # Check each word
        for i, word in enumerate(name_words):
            if word in active_exclusions:
                is_accessory = False
                if word in ALLOW_ACCESSORIES:
                    lookback_range = range(max(0, i-3), i)
                    for j in lookback_range:
                        if name_words[j] in ['with', 'including', 'and', '+']:
                            is_accessory = True
                            break
                if not is_accessory:
                    logger.info(f"Excluding '{name}' because word '{word}' is not introduced as an accessory (no 'with'/'including'/'and' preceding it)")
                    return False
                    
        # 4. Standard head-noun post-modifier rejection on the product name
        last_match_idx = -1
        for i, word in enumerate(name_words):
            for p_type in requested_types:
                variations = self._get_product_type_variations(p_type)
                if any(var == word or (len(word) > len(var) and word.startswith(var)) for var in variations):
                    last_match_idx = i
                    
        if last_match_idx != -1:
            for i, word in enumerate(name_words[last_match_idx + 1:], start=last_match_idx + 1):
                if word in active_exclusions:
                    is_accessory = False
                    if word in ALLOW_ACCESSORIES:
                        lookback_range = range(max(0, i-3), i)
                        for j in lookback_range:
                            if name_words[j] in ['with', 'including', 'and', '+']:
                                is_accessory = True
                                break
                    if not is_accessory:
                        logger.info(f"Excluding '{name}' because it is modified by '{word}' (post-modifier check)")
                        return False
                        
        return True
    
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
                
            # Apply product type name boost: +0.3 if the product type keyword matches in the name
            if matched and keyword.lower() in self.KNOWN_PRODUCT_TYPES:
                if any(var in product_name for var in vars):
                    keyword_score += 0.3
                    
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
        sport: Optional[str] = None,
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
            
            # Filter by sport (optional)
            if sport:
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
                    kw_lower = keyword.lower()
                    if kw_lower in self.KNOWN_PRODUCT_TYPES:
                        # Product type keyword: must match in name OR category (not solely description)
                        keyword_conditions.append(
                            "to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(category_level_1, '') || ' ' || COALESCE(category_level_2, '')) @@ plainto_tsquery('english', %s)"
                        )
                    else:
                        # Non-product type keyword: can match in name OR description
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
        top_k: int = 10,
        fallback_step: int = 0
    ) -> List[Dict]:
        """
        TRUE HYBRID RANKING: Combine keyword and semantic scores with precision validations.
        
        Formula:
            final_score = (semantic_score * 0.6) + (keyword_score * 0.4)
        """
        if not candidate_products:
            return []
        
        logger.info("=" * 80)
        logger.info("HYBRID RANKING")
        logger.info(f"Query: {query_text}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Candidates: {len(candidate_products)}")
        logger.info("=" * 80)
        
        # Determine requested product types from keywords
        requested_product_types = []
        if keywords:
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in self.KNOWN_PRODUCT_TYPES:
                    requested_product_types.append(kw_lower)
        has_product_type = len(requested_product_types) > 0
        
        # Calculate keyword scores first to allow early exit
        candidate_keyword_scores = {}
        has_any_keyword_match = False
        
        for product in candidate_products:
            pid = product['product_id']
            kw_score = self.calculate_keyword_score(product, keywords)
            candidate_keyword_scores[pid] = kw_score
            if kw_score > 0.0:
                has_any_keyword_match = True
                
        if keywords and not has_any_keyword_match:
            logger.info("Zero keyword match among all candidates. Returning empty results immediately.")
            return []
            
        # Get semantic scores
        semantic_scores = self.semantic_search(query_text, candidate_products)
        
        # Combine scores and apply validations
        ranked_products = []
        
        for product in candidate_products:
            product_id = product['product_id']
            product_name = product['name']
            
            # Get semantic score
            semantic_score = semantic_scores.get(product_id, 0.0)
            
            # Get pre-calculated keyword score
            keyword_score = candidate_keyword_scores.get(product_id, 0.0)
            
            # Calculate final hybrid score
            final_score = (semantic_score * self.SEMANTIC_WEIGHT) + (keyword_score * self.KEYWORD_WEIGHT)
            
            # Threshold checks:
            # 1. final_score < 0.15 -> Reject
            if final_score < 0.15:
                logger.info(f"Rejecting '{product_name}' [id={product_id}] due to final_score {final_score:.4f} < 0.15")
                continue
                
            # 2. keyword_score == 0.0 when keywords were provided -> Reject
            if keywords and keyword_score == 0.0:
                logger.info(f"Rejecting '{product_name}' [id={product_id}] due to keyword_score == 0.0 when keywords were provided")
                continue
                
            # 3. Product type validation
            if has_product_type and not self._matches_product_type(
                product_name, 
                product.get('description'), 
                requested_product_types,
                product.get('category_level_1', ''),
                product.get('category_level_2', '')
            ):
                logger.info(f"Rejecting '{product_name}' [id={product_id}] because it does not match requested product type(s): {requested_product_types}")
                continue
            
            # Add scores to product
            product_with_scores = product.copy()
            product_with_scores['semantic_score'] = round(semantic_score, 4)
            product_with_scores['keyword_score'] = round(keyword_score, 4)
            product_with_scores['final_score'] = round(final_score, 4)
            
            ranked_products.append(product_with_scores)
        
        # Sort by final score (descending)
        ranked_products.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Log top results with detailed diagnostics (Change 6)
        logger.info("TOP RANKED PRODUCTS:")
        for i, p in enumerate(ranked_products[:top_k], 1):
            pname = p['name']
            pid = p['product_id']
            pdesc = self._safe_lower(p.get('description'))
            
            # Reconstruct diagnostic info
            matched_keywords = []
            for kw in (keywords or []):
                kw_lower = kw.lower()
                vars = self._get_product_type_variations(kw_lower)
                if any(var in pname.lower() for var in vars):
                    matched_keywords.append(f"{kw}(name)")
                elif any(var in pdesc for var in vars):
                    matched_keywords.append(f"{kw}(desc)")
                    
            product_type_match = "NO"
            if has_product_type:
                matched_types = []
                for p_type in requested_product_types:
                    vars = self._get_product_type_variations(p_type)
                    if any(var in pname.lower() for var in vars):
                        matched_types.append(f"{p_type} in name")
                    elif any(var in pdesc for var in vars):
                        matched_types.append(f"{p_type} in desc")
                if matched_types:
                    product_type_match = f"YES ({', '.join(matched_types)})"
                    
            logger.info(f"RESULT {i}: \"{pname}\" [product_id={pid}]")
            logger.info(f"  semantic={p['semantic_score']:.2f}  keyword={p['keyword_score']:.2f}  final={p['final_score']:.2f}")
            logger.info(f"  matched_keywords: {', '.join(matched_keywords)}")
            logger.info(f"  product_type_match: {product_type_match}")
            logger.info(f"  fallback_step: {fallback_step}")
        logger.info("=" * 80)
        
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
        TRUE HYBRID SEARCH: keyword scoring + semantic scoring + SLM validation.
        """
        logger.info("=" * 80)
        logger.info("HYBRID SEARCH REQUEST")
        logger.info(f"Sport: {sport}")
        logger.info(f"Category L1: {category_level_1}")
        logger.info(f"Category L2: {category_level_2}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Price Limit: {price_limit}")
        logger.info("=" * 80)
        
        # Determine requested product types from keywords
        product_type = None
        is_broad_query = False
        if keywords:
            for kw in keywords:
                if kw.lower() in self.BROAD_QUERY_MODIFIERS:
                    is_broad_query = True
                    break
            
            if not is_broad_query:
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in self.KNOWN_PRODUCT_TYPES:
                        product_type = kw_lower
                        break
        
        has_product_type = product_type is not None
        
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
        
        # Step 4 & 5: Sport-only fallback OR Relaxed sport keyword fallback
        if not candidates:
            if has_product_type:
                logger.warning(f"No candidates found in sport {sport} with keywords. Relaxing sport filter to search for product type across all sports.")
                candidates = self.keyword_filter(
                    sport=None,
                    category_level_1=None,
                    category_level_2=None,
                    keywords=keywords,
                    price_limit=price_limit,
                    limit=100,
                    keyword_mode='OR'
                )
                fallback_step = 5
                if candidates:
                    logger.info(f"✓ Step 5 (OR keywords, relaxed sport filter): {len(candidates)} candidates")
            else:
                logger.warning("No keyword candidates and no product type detected, falling back to sport-only")
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
        query_parts = []
        if sport:
            query_parts.append(sport)
        if category_level_1:
            query_parts.append(category_level_1)
        if category_level_2:
            query_parts.append(category_level_2)
        if keywords:
            query_parts.extend(keywords)
            
        query_text = " ".join(query_parts)
        
        # Set candidate limit: 15 for SLM validation to prevent latency bottleneck
        top_k_candidates = 15 if has_product_type else top_k
        
        # Hybrid ranking (keyword + semantic)
        ranked_products = self.hybrid_rank(
            query_text=query_text,
            keywords=keywords or [],
            candidate_products=candidates,
            top_k=top_k_candidates,
            fallback_step=fallback_step
        )
        
        if not ranked_products:
            if has_product_type:
                logger.info(f"No products matching product type '{product_type}' found. Returning empty results rather than unrelated products.")
            else:
                logger.info("No products found matching the query criteria.")
            return []
            
        # SLM Validation and Re-Ranking Layer
        if has_product_type:
            logger.info(f"SLM product validation enabled for product type: '{product_type}'")
            validation_decisions = self.validation_service.validate_products(product_type, ranked_products)
            
            # Safe Fallback (No fail-open): if offline, fall back directly to original hybrid ranking
            if validation_decisions is None:
                logger.warning("SLM validation service failed or offline. Falling back to default hybrid ranking (no validation).")
                return ranked_products[:top_k]
                
            # Create lookup map for decisions
            decisions_map = {str(d.get("id")): d for d in validation_decisions}
            
            # Log detailed diagnostics for each candidate (Change 5 & 7)
            logger.info("=" * 80)
            logger.info("VALIDATION RESULT")
            logger.info(f"Query: {' '.join(keywords) if keywords else ''}")
            logger.info(f"Requested Product Type: {product_type}")
            logger.info("=" * 80)
            for p in ranked_products:
                pid = str(p['product_id'])
                d_info = decisions_map.get(pid, {"decision": "NOT_RELEVANT", "confidence": 0.0, "reason": "No decision returned from SLM"})
                logger.info(f"Candidate: {p['name']}")
                logger.info(f"Decision: {d_info.get('decision')}")
                logger.info(f"Confidence: {d_info.get('confidence')}")
                logger.info(f"Reason: {d_info.get('reason')}")
                logger.info("-" * 40)
            logger.info("=" * 80)
            
            relevant_products = []
            related_products = []
            
            for p in ranked_products:
                pid = str(p['product_id'])
                d_info = decisions_map.get(pid)
                if not d_info:
                    continue
                    
                decision = d_info.get("decision", "NOT_RELEVANT").upper()
                confidence = float(d_info.get("confidence", 0.0))
                
                if decision not in ("RELEVANT", "RELATED"):
                    continue
                    
                # Update final score using formula: 0.7 * hybrid_score + 0.3 * validation_confidence
                p_copy = p.copy()
                hybrid_score = float(p.get("final_score", 0.0))
                new_final_score = round((hybrid_score * 0.7) + (confidence * 0.3), 4)
                p_copy["final_score"] = new_final_score
                p_copy["validation_confidence"] = confidence
                p_copy["validation_reason"] = d_info.get("reason", "")
                p_copy["validation_decision"] = decision
                
                if decision == "RELEVANT":
                    relevant_products.append(p_copy)
                elif decision == "RELATED":
                    related_products.append(p_copy)
            
            # Sort lists independently by final_score descending
            relevant_products.sort(key=lambda x: x["final_score"], reverse=True)
            related_products.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Combine: RELEVANT first, then RELATED
            final_ranked = relevant_products + related_products
            
            logger.info(f"Validation summary: {len(relevant_products)} RELEVANT, {len(related_products)} RELATED, {len(ranked_products) - len(final_ranked)} NOT_RELEVANT")
            
            return final_ranked[:top_k]
            
        logger.info(f"✓ Hybrid search returned {len(ranked_products)} products")
        return ranked_products[:top_k]
