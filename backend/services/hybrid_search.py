"""
Hybrid Search Service
TRUE Hybrid Search: Combines keyword matching scores with semantic similarity

Architecture (High-Recall Retrieval Pipeline):
    User Query
    ↓
    Intent Parser (external - not modified here)
    ↓
    Broad SQL Candidate Generation (High Recall)
    ↓
    Semantic Ranking (pgvector)
    ↓
    LLM Validation (High Precision)
    ↓
    Final Results

Scoring Formula:
    final_score = (semantic_score * 0.6) + (keyword_score * 0.4)

Keyword Scoring Priority:
    - Product Name Match: 1.0 (highest priority)
    - Exact Match Boost: +0.2
    - Description Match: 0.3
    - All Keywords Match Bonus: +0.3

SQL is responsible ONLY for broad candidate generation.
Precision filtering is handled by semantic ranking and the LLM validator.
"""
import logging
from typing import List, Dict, Optional, Tuple, Union
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
    1. Broad SQL Candidate Generation (high recall)
    2. Keyword Scoring (name, description matching)
    3. Semantic Scoring (vector similarity)
    4. LLM Validation (high precision)
    
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
        self.validation_service = ProductValidationService()
        
    def _get_variations(self, word: str) -> List[str]:
        """Generate singular/plural variations of a word."""
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
    
    def _identify_intent_keywords(self, keywords: List[str]) -> Tuple[List[str], List[str]]:
        """
        Split keywords into 'core intent' and 'descriptive modifiers'.
        
        Core intent keywords are the ones most likely to identify the product type
        (nouns). Descriptive modifiers are adjectives/attributes (e.g. 'waterproof',
        'lightweight', 'men', 'kids').
        
        This is a lightweight heuristic — not a full NLP parser. It identifies
        common descriptive words and treats the rest as core intent.
        
        Returns:
            (core_keywords, descriptive_keywords)
        """
        DESCRIPTIVE_WORDS = {
            'waterproof', 'water', 'repellent', 'resistant', 'lightweight', 'heavy',
            'men', 'mens', 'women', 'womens', 'kids', 'junior', 'senior',
            'large', 'small', 'medium', 'xl', 'xxl',
            'red', 'blue', 'green', 'black', 'white', 'yellow', 'pink', 'grey', 'gray',
            'cheap', 'premium', 'pro', 'professional', 'beginner',
            'outdoor', 'indoor', 'foldable', 'portable', 'compact',
            'under', 'above', 'below',
        }
        
        core = []
        descriptive = []
        for kw in keywords:
            if kw.lower() in DESCRIPTIVE_WORDS:
                descriptive.append(kw)
            else:
                core.append(kw)
        
        # If ALL keywords were classified as descriptive (unlikely but possible),
        # treat them all as core to avoid an empty core set
        if not core:
            core = keywords[:]
            descriptive = []
        
        return core, descriptive
    
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
        plus a small bonus for matching multiple keywords.
        
        NULL-SAFE: Handles None values in all product fields.
        
        Returns score in range [0.0, 1.5]
        """
        if not keywords:
            return 0.5  # Neutral score if no keywords
        
        # NULL-SAFE: Use _safe_lower to handle None
        product_name = self._safe_lower(product.get('name'))
        description = self._safe_lower(product.get('description'))
        cat1_lower = self._safe_lower(product.get('category_level_1'))
        
        individual_scores = []
        unique_matches = 0
        
        for keyword in keywords:
            vars = self._get_variations(keyword)
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
        sport: Optional[str] = None,
        category_level_1: Optional[str] = None,
        category_level_2: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        price_limit: Optional[float] = None,
        limit: int = 100,
        keyword_mode: str = 'AND',
        stage_name: str = "SQL"
    ) -> List[Dict]:
        """
        Broad SQL candidate generation.
        
        Purpose: Generate a large candidate pool with HIGH RECALL.
        SQL applies only inexpensive structured filters (sport, price, gender, category)
        and keyword matching across name + description.
        
        SQL does NOT perform precision filtering — that is the job of semantic
        ranking and the LLM validator.
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
            
            # Full-text search: precise word matching with stemming (name, description OR category)
            # plainto_tsquery safely handles any user input
            # Stemming: "clubs" matches "club", "running" matches "run"
            if keywords and len(keywords) > 0:
                keyword_conditions = []
                for keyword in keywords:
                    # Search name, description, and categories to maximize recall
                    keyword_conditions.append(
                        "to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '') || ' ' || COALESCE(category_level_1, '') || ' ' || COALESCE(category_level_2, '')) @@ plainto_tsquery('english', %s)"
                    )
                    params.append(keyword)
                
                # AND mode: product must contain ALL keywords; OR mode: any keyword
                joiner = " AND " if keyword_mode == 'AND' else " OR "
                query += " AND (" + joiner.join(keyword_conditions) + ")"
            
            # Order by rating and limit
            query += " ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST"
            query += f" LIMIT {limit}"
            
            logger.info("🔍" + "=" * 79)
            logger.info(f"📊 SQL STAGE: {stage_name}")
            logger.info(f"   Sport: {sport}")
            logger.info(f"   Category L1: {category_level_1}")
            logger.info(f"   Category L2: {category_level_2}")
            logger.info(f"   Keywords: {keywords}")
            logger.info(f"   Price limit: {price_limit}")
            logger.info(f"   Keyword mode: {keyword_mode}")
            logger.info(f"   SQL Query: {query}")
            logger.info(f"   SQL Params: {params}")
            
            cur.execute(query, params)
            results = cur.fetchall()
            
            logger.info(f"✅ SQL RETURNED: {len(results)} candidates")
            
            if results:
                logger.info("📦 CANDIDATE DETAILS:")
                for idx, r in enumerate(results[:20], 1):  # Log first 20
                    logger.info(f"   {idx}. ID={r['product_id']} | {r['name']} | Price=₹{r['price']}")
                if len(results) > 20:
                    logger.info(f"   ... and {len(results) - 20} more")
            else:
                logger.warning("⚠️  NO SQL CANDIDATES RETURNED")
            
            logger.info("=" * 80)
            
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
            logger.warning("⚠️  SEMANTIC SEARCH: No candidates to score")
            return {}
        
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("🧠" + "=" * 79)
            logger.info(f"🧠 SEMANTIC SEARCH STAGE")
            logger.info(f"   Query text: {query_text}")
            logger.info(f"   Input candidates: {len(candidate_products)}")
            
            # Generate query embedding
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
            
            logger.info(f"✅ SEMANTIC SCORES COMPUTED: {len(similarity_map)} products scored")
            
            if similarity_map:
                # Show top 10 scores
                sorted_scores = sorted(similarity_map.items(), key=lambda x: x[1], reverse=True)[:10]
                logger.info("🎯 TOP 10 SEMANTIC SCORES:")
                for pid, score in sorted_scores:
                    prod_name = next((p['name'] for p in candidate_products if p['product_id'] == pid), 'Unknown')
                    logger.info(f"   {score:.4f} | ID={pid} | {prod_name}")
            
            logger.info("=" * 80)
            
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
        
        This method scores and ranks candidates. It does NOT perform precision
        filtering — that is handled downstream by the LLM validator.
        
        Formula:
            final_score = (semantic_score * 0.6) + (keyword_score * 0.4)
        """
        if not candidate_products:
            logger.warning("⚠️  HYBRID RANKING: No candidates to rank")
            return []
        
        logger.info("⚡" + "=" * 79)
        logger.info("⚡ HYBRID RANKING STAGE")
        logger.info(f"   Query: {query_text}")
        logger.info(f"   Keywords: {keywords}")
        logger.info(f"   Input candidates: {len(candidate_products)}")
        logger.info("=" * 80)
        
        # Calculate keyword scores
        candidate_keyword_scores = {}
        for product in candidate_products:
            pid = product['product_id']
            kw_score = self.calculate_keyword_score(product, keywords)
            candidate_keyword_scores[pid] = kw_score
                
        # Get semantic scores
        semantic_scores = self.semantic_search(query_text, candidate_products)
        
        # Combine scores
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
            
            # Minimum threshold: reject products with extremely low combined relevance
            if final_score < 0.15:
                logger.debug(f"Rejecting '{product_name}' [id={product_id}] due to final_score {final_score:.4f} < 0.15")
                continue
            
            # Add scores to product
            product_with_scores = product.copy()
            product_with_scores['semantic_score'] = round(semantic_score, 4)
            product_with_scores['keyword_score'] = round(keyword_score, 4)
            product_with_scores['final_score'] = round(final_score, 4)
            
            ranked_products.append(product_with_scores)
        
        # Sort by final score (descending)
        ranked_products.sort(key=lambda x: x['final_score'], reverse=True)
        
        logger.info(f"✅ HYBRID RANKING COMPLETE: {len(ranked_products)} products ranked")
        logger.info(f"   Products passing threshold (score >= 0.15): {len(ranked_products)}")
        
        # Log top results
        logger.info(f"🏆 TOP {min(top_k, len(ranked_products))} RANKED PRODUCTS:")
        for i, p in enumerate(ranked_products[:top_k], 1):
            pname = p['name']
            pid = p['product_id']
            logger.info(f"   {i}. ID={pid} | {pname}")
            logger.info(f"      semantic={p['semantic_score']:.4f} | keyword={p['keyword_score']:.4f} | final={p['final_score']:.4f}")
        
        logger.info("=" * 80)
        
        return ranked_products[:top_k]

    def search(
        self,
        sport: str,
        category_level_1: Optional[str] = None,
        category_level_2: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        price_limit: Optional[float] = None,
        top_k: int = 10,
        return_format: str = 'dict'
    ) -> Union[Dict[str, List[Dict]], List[Dict]]:
        """
        Main search entry point.
        
        Pipeline:
            1. Broad SQL Candidate Generation (progressive relaxation)
            2. Hybrid Ranking (keyword + semantic scoring)
            3. LLM Validation (precision filtering for product-type queries)
        
        Args:
            return_format: 'dict' returns {'relevant': [...], 'related': [...]} (for external API)
                          'flat' returns flat list of RELEVANT products only (for backward compatibility)
        
        Returns:
            Dict with 'relevant' and 'related' keys if return_format='dict'
            List of RELEVANT products if return_format='flat'
        """
        logger.info("=" * 80)
        logger.info("HYBRID SEARCH REQUEST")
        logger.info(f"Sport: {sport}")
        logger.info(f"Category L1: {category_level_1}")
        logger.info(f"Category L2: {category_level_2}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Price Limit: {price_limit}")
        logger.info("=" * 80)
        
        # =====================================================================
        # STAGE 1: Broad SQL Candidate Generation with Progressive Relaxation
        # =====================================================================
        # SQL is ONLY responsible for generating a broad candidate pool.
        # It maximizes recall, not precision.
        
        candidates = []
        seen_ids = set()
        retrieval_stages = []
        TARGET_POOL_SIZE = 40
        
        logger.info("🚀" + "=" * 79)
        logger.info("🚀 RETRIEVAL PIPELINE START")
        logger.info("=" * 80)
        
        def add_candidates(new_list: List[Dict], stage_name: str) -> bool:
            added_count = 0
            for item in new_list:
                pid = item['product_id']
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    candidates.append(item)
                    added_count += 1
            if added_count > 0:
                retrieval_stages.append(f"{stage_name}(+{added_count})")
                logger.info(f"✅ Stage '{stage_name}' added {added_count} new candidates (Total pool: {len(candidates)})")
                return True
            else:
                logger.info(f"⏭️  Stage '{stage_name}' SKIPPED (no new candidates)")
                return False
        
        if keywords:
            # Separate core intent keywords from descriptive modifiers
            core_keywords, descriptive_keywords = self._identify_intent_keywords(keywords)
            
            logger.info("🔍 KEYWORD ANALYSIS:")
            logger.info(f"   All keywords: {keywords}")
            logger.info(f"   Core keywords: {core_keywords}")
            logger.info(f"   Descriptive keywords: {descriptive_keywords}")
            logger.info(f"   Target pool size: {TARGET_POOL_SIZE}")
            logger.info("=" * 80)
            
            # --- Stage 1: All keywords (AND) + structured filters ---
            logger.info(">>> ENTERING Stage 1")
            if len(candidates) < TARGET_POOL_SIZE:
                logger.info("🔹 Attempting Stage 1: All keywords (AND) + structured filters")
                logger.info(f"   Condition check: len(candidates)={len(candidates)} < TARGET={TARGET_POOL_SIZE} ✓")
                stage_candidates = self.keyword_filter(
                    sport=sport,
                    category_level_1=category_level_1,
                    category_level_2=category_level_2,
                    keywords=keywords,
                    price_limit=price_limit,
                    limit=100,
                    keyword_mode='AND',
                    stage_name="Stage_1_all_keywords_AND"
                )
                add_candidates(stage_candidates, '1_all_keywords_AND')
            else:
                logger.info("⏭️  Stage 1 SKIPPED (target pool size reached)")
            logger.info(f"<<< EXITING Stage 1: candidates={len(candidates)}")
            
            logger.info(f"📊 After Stage 1: candidates={len(candidates)}")
            
            # --- Stage 1b: All keywords (AND) + drop category filters ---
            logger.info(">>> ENTERING Stage 1b")
            if len(candidates) < TARGET_POOL_SIZE and (category_level_1 or category_level_2):
                logger.info("🔹 Attempting Stage 1b: All keywords (AND) + drop category")
                logger.info(f"   Condition: len(candidates)={len(candidates)} < TARGET={TARGET_POOL_SIZE} ✓")
                logger.info(f"   Condition: has categories to drop ✓")
                stage_candidates = self.keyword_filter(
                    sport=sport,
                    keywords=keywords,
                    price_limit=price_limit,
                    limit=100,
                    keyword_mode='AND',
                    stage_name="Stage_1b_all_keywords_AND_no_category"
                )
                add_candidates(stage_candidates, '1b_all_keywords_AND_no_category')
            else:
                if len(candidates) >= TARGET_POOL_SIZE:
                    logger.info("⏭️  Stage 1b SKIPPED (target pool size reached)")
                else:
                    logger.info("⏭️  Stage 1b SKIPPED (no categories to drop)")
            logger.info(f"<<< EXITING Stage 1b: candidates={len(candidates)}")
            
            logger.info(f"📊 After Stage 1b: candidates={len(candidates)}")
            
            # --- Stage 2: Relax descriptive keywords, keep core intent ---
            logger.info(">>> ENTERING Stage 2")
            logger.info("=" * 80)
            logger.info("🔍 STAGE 2 CONDITION CHECK - RUNTIME VALUES:")
            logger.info(f"   len(candidates) = {len(candidates)}")
            logger.info(f"   TARGET_POOL_SIZE = {TARGET_POOL_SIZE}")
            logger.info(f"   core_keywords = {core_keywords}")
            logger.info(f"   descriptive_keywords = {descriptive_keywords}")
            logger.info(f"   keywords = {keywords}")
            logger.info(f"   len(core_keywords) = {len(core_keywords)}")
            logger.info(f"   len(keywords) = {len(keywords)}")
            logger.info("")
            
            stage2_cond1_pool_size = len(candidates) < TARGET_POOL_SIZE
            stage2_cond2_has_descriptive = bool(descriptive_keywords)
            stage2_cond3_core_less_than_all = len(core_keywords) < len(keywords)
            stage2_cond2_full = descriptive_keywords and len(core_keywords) < len(keywords)
            stage2_execute = stage2_cond1_pool_size and stage2_cond2_full
            
            logger.info(f"   Condition 1 (pool size check): len(candidates) < TARGET_POOL_SIZE = {stage2_cond1_pool_size}")
            logger.info(f"   Condition 2a (has descriptive): bool(descriptive_keywords) = {stage2_cond2_has_descriptive}")
            logger.info(f"   Condition 2b (core < all): len(core_keywords) < len(keywords) = {stage2_cond3_core_less_than_all}")
            logger.info(f"   Condition 2 (combined): descriptive_keywords AND core<all = {stage2_cond2_full}")
            logger.info("")
            logger.info(f"   FINAL Stage 2 decision: {'EXECUTE' if stage2_execute else 'SKIP'}")
            logger.info("=" * 80)
            
            if stage2_execute:
                candidates_before_stage2 = len(candidates)
                logger.info("🔹 Attempting Stage 2a: Core keywords (AND) + structured filters")
                logger.info(f"   Core keywords: {core_keywords}")
                logger.info(f"   Descriptive keywords (dropped): {descriptive_keywords}")
                # Stage 2a: Core keywords (AND) + structured filters
                stage_candidates = self.keyword_filter(
                    sport=sport,
                    category_level_1=category_level_1,
                    category_level_2=category_level_2,
                    keywords=core_keywords,
                    price_limit=price_limit,
                    limit=100,
                    keyword_mode='AND',
                    stage_name="Stage_2a_core_keywords_AND"
                )
                stage2a_added = add_candidates(stage_candidates, '2a_core_keywords_AND')
                
                logger.info(f"   Stage 2a results:")
                logger.info(f"      Candidates before: {candidates_before_stage2}")
                logger.info(f"      Candidates after: {len(candidates)}")
                logger.info(f"      New products added: {len(candidates) - candidates_before_stage2}")
                if stage2a_added:
                    logger.info(f"      IDs of new products:")
                    new_products = candidates[candidates_before_stage2:]
                    for idx, p in enumerate(new_products[:20], 1):
                        logger.info(f"         {idx}. ID={p['product_id']} | {p['name']}")
                
                # Stage 2b: Core keywords (AND) + drop category
                logger.info(">>> ENTERING Stage 2b")
                candidates_before_stage2b = len(candidates)
                if len(candidates) < TARGET_POOL_SIZE and (category_level_1 or category_level_2):
                    logger.info("🔹 Attempting Stage 2b: Core keywords (AND) + drop category")
                    stage_candidates = self.keyword_filter(
                        sport=sport,
                        keywords=core_keywords,
                        price_limit=price_limit,
                        limit=100,
                        keyword_mode='AND',
                        stage_name="Stage_2b_core_keywords_AND_no_category"
                    )
                    stage2b_added = add_candidates(stage_candidates, '2b_core_keywords_AND_no_category')
                    
                    logger.info(f"   Stage 2b results:")
                    logger.info(f"      Candidates before: {candidates_before_stage2b}")
                    logger.info(f"      Candidates after: {len(candidates)}")
                    logger.info(f"      New products added: {len(candidates) - candidates_before_stage2b}")
                    if stage2b_added:
                        logger.info(f"      IDs of new products:")
                        new_products = candidates[candidates_before_stage2b:]
                        for idx, p in enumerate(new_products[:20], 1):
                            logger.info(f"         {idx}. ID={p['product_id']} | {p['name']}")
                else:
                    if len(candidates) >= TARGET_POOL_SIZE:
                        logger.info("⏭️  Stage 2b SKIPPED (target pool size reached)")
                    else:
                        logger.info("⏭️  Stage 2b SKIPPED (no categories to drop)")
                logger.info(f"<<< EXITING Stage 2b: candidates={len(candidates)}")
            else:
                if len(candidates) >= TARGET_POOL_SIZE:
                    logger.info("⏭️  Stage 2 SKIPPED (target pool size reached)")
                elif not descriptive_keywords:
                    logger.info("⏭️  Stage 2 SKIPPED (no descriptive keywords to relax)")
                elif not (len(core_keywords) < len(keywords)):
                    logger.info("⏭️  Stage 2 SKIPPED (all keywords are core, none are descriptive)")
                else:
                    logger.info("⏭️  Stage 2 SKIPPED (unknown reason)")
            
            logger.info(f"<<< EXITING Stage 2: candidates={len(candidates)}")
            logger.info(f"📊 After Stage 2: candidates={len(candidates)}")
            
            # --- Stage 2c: All keywords in OR mode ---
            logger.info(">>> ENTERING Stage 2c")
            logger.info("=" * 80)
            logger.info("🔍 STAGE 2c CONDITION CHECK - RUNTIME VALUES:")
            logger.info(f"   len(candidates) = {len(candidates)}")
            logger.info(f"   TARGET_POOL_SIZE = {TARGET_POOL_SIZE}")
            logger.info(f"   keywords = {keywords}")
            logger.info("")
            
            stage2c_cond1_pool_size = len(candidates) < TARGET_POOL_SIZE
            stage2c_execute = stage2c_cond1_pool_size
            
            logger.info(f"   Condition 1 (pool size check): len(candidates) < TARGET_POOL_SIZE = {stage2c_cond1_pool_size}")
            logger.info("")
            logger.info(f"   FINAL Stage 2c decision: {'EXECUTE' if stage2c_execute else 'SKIP'}")
            logger.info("=" * 80)
            
            if stage2c_execute:
                candidates_before_stage2c = len(candidates)
                logger.info("🔹 Attempting Stage 2c: All keywords (OR mode)")
                stage_candidates = self.keyword_filter(
                    sport=sport,
                    category_level_1=category_level_1,
                    category_level_2=category_level_2,
                    keywords=keywords,
                    price_limit=price_limit,
                    limit=100,
                    keyword_mode='OR',
                    stage_name="Stage_2c_all_keywords_OR"
                )
                stage2c_added = add_candidates(stage_candidates, '2c_all_keywords_OR')
                
                logger.info(f"   Stage 2c results:")
                logger.info(f"      Candidates before: {candidates_before_stage2c}")
                logger.info(f"      Candidates after: {len(candidates)}")
                logger.info(f"      New products added: {len(candidates) - candidates_before_stage2c}")
                if stage2c_added:
                    logger.info(f"      IDs of new products:")
                    new_products = candidates[candidates_before_stage2c:]
                    for idx, p in enumerate(new_products[:20], 1):
                        logger.info(f"         {idx}. ID={p['product_id']} | {p['name']}")
                
                # Stage 2d: OR mode + drop category
                logger.info(">>> ENTERING Stage 2d")
                candidates_before_stage2d = len(candidates)
                if len(candidates) < TARGET_POOL_SIZE and (category_level_1 or category_level_2):
                    logger.info("🔹 Attempting Stage 2d: All keywords (OR) + drop category")
                    stage_candidates = self.keyword_filter(
                        sport=sport,
                        keywords=keywords,
                        price_limit=price_limit,
                        limit=100,
                        keyword_mode='OR',
                        stage_name="Stage_2d_all_keywords_OR_no_category"
                    )
                    stage2d_added = add_candidates(stage_candidates, '2d_all_keywords_OR_no_category')
                    
                    logger.info(f"   Stage 2d results:")
                    logger.info(f"      Candidates before: {candidates_before_stage2d}")
                    logger.info(f"      Candidates after: {len(candidates)}")
                    logger.info(f"      New products added: {len(candidates) - candidates_before_stage2d}")
                    if stage2d_added:
                        logger.info(f"      IDs of new products:")
                        new_products = candidates[candidates_before_stage2d:]
                        for idx, p in enumerate(new_products[:20], 1):
                            logger.info(f"         {idx}. ID={p['product_id']} | {p['name']}")
                else:
                    if len(candidates) >= TARGET_POOL_SIZE:
                        logger.info("⏭️  Stage 2d SKIPPED (target pool size reached)")
                    else:
                        logger.info("⏭️  Stage 2d SKIPPED (no categories to drop)")
                logger.info(f"<<< EXITING Stage 2d: candidates={len(candidates)}")
            else:
                logger.info("⏭️  Stage 2c/2d SKIPPED (target pool size reached)")
            
            logger.info(f"<<< EXITING Stage 2c: candidates={len(candidates)}")
            logger.info(f"📊 After Stage 2c/2d: candidates={len(candidates)}")
        
        # --- Stage 3: Structured filters only (no keywords) ---
        # Let semantic search rank the entire sport's catalog
        logger.info(">>> ENTERING Stage 3")
        logger.info("=" * 80)
        logger.info("🔍 STAGE 3 CONDITION CHECK - RUNTIME VALUES:")
        logger.info(f"   len(candidates) = {len(candidates)}")
        logger.info(f"   TARGET_POOL_SIZE = {TARGET_POOL_SIZE}")
        logger.info(f"   sport = {sport}")
        logger.info(f"   category_level_1 = {category_level_1}")
        logger.info(f"   category_level_2 = {category_level_2}")
        logger.info("")
        
        stage3_cond1_pool_size = len(candidates) < TARGET_POOL_SIZE
        stage3_execute = stage3_cond1_pool_size
        
        logger.info(f"   Condition 1 (pool size check): len(candidates) < TARGET_POOL_SIZE = {stage3_cond1_pool_size}")
        logger.info("")
        logger.info(f"   FINAL Stage 3 decision: {'EXECUTE' if stage3_execute else 'SKIP'}")
        logger.info("=" * 80)
        
        if stage3_execute:
            candidates_before_stage3 = len(candidates)
            logger.info("🔹 Attempting Stage 3: Structured filters only (no keywords)")
            stage_candidates = self.keyword_filter(
                sport=sport,
                category_level_1=category_level_1,
                category_level_2=category_level_2,
                keywords=None,
                price_limit=price_limit,
                limit=100,
                stage_name="Stage_3_structured_only"
            )
            stage3_added = add_candidates(stage_candidates, '3_structured_only')
            
            logger.info(f"   Stage 3 results:")
            logger.info(f"      Candidates before: {candidates_before_stage3}")
            logger.info(f"      Candidates after: {len(candidates)}")
            logger.info(f"      New products added: {len(candidates) - candidates_before_stage3}")
            if stage3_added:
                logger.info(f"      IDs of new products:")
                new_products = candidates[candidates_before_stage3:]
                for idx, p in enumerate(new_products[:20], 1):
                    logger.info(f"         {idx}. ID={p['product_id']} | {p['name']}")
            
            # Stage 3b: Sport + price only
            logger.info(">>> ENTERING Stage 3b")
            candidates_before_stage3b = len(candidates)
            if len(candidates) < TARGET_POOL_SIZE and (category_level_1 or category_level_2):
                logger.info("🔹 Attempting Stage 3b: Sport + price only (drop categories)")
                stage_candidates = self.keyword_filter(
                    sport=sport,
                    keywords=None,
                    price_limit=price_limit,
                    limit=100,
                    stage_name="Stage_3b_sport_price_only"
                )
                stage3b_added = add_candidates(stage_candidates, '3b_sport_price_only')
                
                logger.info(f"   Stage 3b results:")
                logger.info(f"      Candidates before: {candidates_before_stage3b}")
                logger.info(f"      Candidates after: {len(candidates)}")
                logger.info(f"      New products added: {len(candidates) - candidates_before_stage3b}")
                if stage3b_added:
                    logger.info(f"      IDs of new products:")
                    new_products = candidates[candidates_before_stage3b:]
                    for idx, p in enumerate(new_products[:20], 1):
                        logger.info(f"         {idx}. ID={p['product_id']} | {p['name']}")
            else:
                if len(candidates) >= TARGET_POOL_SIZE:
                    logger.info("⏭️  Stage 3b SKIPPED (target pool size reached)")
                else:
                    logger.info("⏭️  Stage 3b SKIPPED (no categories to drop)")
            logger.info(f"<<< EXITING Stage 3b: candidates={len(candidates)}")
        else:
            logger.info("⏭️  Stage 3 SKIPPED (target pool size reached)")
        
        logger.info(f"<<< EXITING Stage 3: candidates={len(candidates)}")
        logger.info(f"📊 After Stage 3: candidates={len(candidates)}")
        
        if not candidates:
            logger.error(f"❌ NO CANDIDATES FOUND after all retrieval stages for sport={sport}")
            return []
        
        retrieval_stage_str = ", ".join(retrieval_stages) if retrieval_stages else "none"
        logger.info("=" * 80)
        logger.info(f"✅ RETRIEVAL COMPLETE: {len(candidates)} total candidates")
        logger.info(f"   Retrieval stages used: {retrieval_stage_str}")
        logger.info("=" * 80)
        
        # =====================================================================
        # STAGE 2: Hybrid Ranking (Keyword + Semantic Scoring)
        # =====================================================================
        
        logger.info(">>> ENTERING HYBRID RANKING")
        
        # Build semantic query text — include sport for context
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
        
        # For search intents: send top 25 candidates to SLM validator
        # For task intents: keep at top_k (usually 20 from task tool)
        # Search intents benefit more from increased validation because they're
        # interactive user queries where recall is critical.
        # Task intents already iterate multiple times (one per item), so keeping
        # validation focused is better for performance.
        if return_format == 'dict':
            # Search intent: increase to 25 for better recall
            ranking_limit = 25
        else:
            # Task intent: use top_k (typically 20)
            ranking_limit = top_k
        
        ranked_products = self.hybrid_rank(
            query_text=query_text,
            keywords=keywords or [],
            candidate_products=candidates,
            top_k=ranking_limit
        )
        
        logger.info(f"<<< EXITING HYBRID RANKING: {len(ranked_products)} products ranked")
        
        if not ranked_products:
            logger.info("No products survived hybrid ranking.")
            return {'relevant': [], 'related': []}
        
        # =====================================================================
        # STAGE 3: LLM Validation (High Precision)
        # =====================================================================
        # The validator decides RELEVANT / RELATED / NOT_RELEVANT.
        # This is where precision filtering happens — NOT in SQL.
        
        logger.info(">>> ENTERING LLM VALIDATION")
        
        # =====================================================================
        # CANONICAL PRODUCT EXTRACTION
        # =====================================================================
        # Identifies the canonical product phrase from keywords by filtering out
        # adjectives and attributes that are search filters, not product names.
        #
        # This is NOT simple concatenation - it identifies the actual product.
        #
        # Examples:
        #   Keywords                              → Canonical Product
        #   ["golf", "club"]                      → "golf club"
        #   ["football", "shoes"]                 → "football shoes"
        #   ["waterproof", "hiking", "shoes"]     → "hiking shoes"
        #   ["men", "running", "shoes"]           → "running shoes"
        #   ["women", "golf", "shirt"]            → "golf shirt"
        #   ["red", "football", "jersey"]         → "football jersey"
        #
        # Adjectives/attributes are filters (NOT part of the product type):
        #   - Colors: red, blue, green, black, white, yellow, pink, grey
        #   - Gender/age: men, mens, women, womens, kids, junior, senior
        #   - Size: large, small, medium, xl, xxl
        #   - Features: waterproof, lightweight, breathable, durable
        #   - Quality: cheap, premium, pro, professional, beginner
        #   - Modifiers: best, top, good, show, me, find, get
        
        product_type = None
        if keywords:
            # Comprehensive exclusion set: adjectives, not product nouns
            adjective_filters = {
                # Features
                'waterproof', 'water', 'repellent', 'resistant', 'breathable',
                'lightweight', 'heavy', 'durable', 'flexible', 'stretchy',
                'insulated', 'thermal', 'warm', 'cool', 'soft', 'hard',
                'foldable', 'portable', 'compact', 'collapsible',
                # Gender/Age
                'men', 'mens', "men's", 'women', 'womens', "women's",
                'kids', 'junior', 'senior', 'youth', 'adult', 'unisex',
                'boys', 'girls', 'toddler', 'infant',
                # Size
                'large', 'small', 'medium', 'xl', 'xxl', 'xs', 's', 'm', 'l',
                'big', 'tiny', 'mini', 'maxi', 'oversized',
                # Colors
                'red', 'blue', 'green', 'black', 'white', 'yellow',
                'pink', 'grey', 'gray', 'orange', 'purple', 'brown',
                'navy', 'maroon', 'beige', 'tan', 'silver', 'gold',
                # Quality/Price
                'cheap', 'expensive', 'premium', 'pro', 'professional',
                'beginner', 'intermediate', 'advanced', 'elite',
                'budget', 'affordable', 'luxury', 'basic', 'standard',
                # Location/Use
                'outdoor', 'indoor', 'home', 'gym', 'travel', 'office',
                # Action words
                'under', 'above', 'below', 'less', 'more', 'around',
                'show', 'me', 'find', 'get', 'need', 'want', 'looking',
                'best', 'top', 'good', 'great', 'excellent', 'quality',
                # Material (sometimes filters, not product names)
                'cotton', 'polyester', 'leather', 'synthetic', 'mesh',
                'nylon', 'canvas', 'rubber', 'plastic', 'metal'
            }
            
            # If single keyword, use it directly (already canonical)
            if len(keywords) == 1:
                product_type = keywords[0].lower()
            else:
                # Filter out adjectives/attributes to identify the product phrase
                # This identifies the actual product, not just concatenates words
                product_keywords = [
                    kw for kw in keywords
                    if kw.lower() not in adjective_filters
                ]
                
                if product_keywords:
                    # Join the product phrase components (the actual product words)
                    # Examples:
                    #   ["golf", "club"] → "golf club"
                    #   ["hiking", "shoes"] (from ["waterproof", "hiking", "shoes"]) → "hiking shoes"
                    #   ["running", "shoes"] (from ["men", "running", "shoes"]) → "running shoes"
                    #   ["golf", "shirt"] (from ["women", "golf", "shirt"]) → "golf shirt"
                    product_type = " ".join(product_keywords).lower()
                elif keywords:
                    # Fallback: if all keywords are filters, use them anyway
                    # (Better than returning None)
                    product_type = " ".join(keywords).lower()
        
        if product_type:
            # GRANULAR VALIDATION LOGGING
            logger.info("=" * 80)
            logger.info("VALIDATOR INPUT")
            logger.info(f"Keywords received: {keywords}")
            logger.info(f"Canonical product type extracted: '{product_type}'")
            logger.info(f"Candidates to validate: {len(ranked_products)}")
            logger.info("=" * 80)
            
            logger.info("🤖" + "=" * 79)
            logger.info(f"🤖 LLM VALIDATION STAGE")
            logger.info(f"   Product type requested: '{product_type}'")
            logger.info(f"   Candidates to validate: {len(ranked_products)}")
            logger.info("=" * 80)
            
            validation_decisions = self.validation_service.validate_products(product_type, ranked_products)
            
            # Safe Fallback: if validator is offline, only return products that
            # have keyword_score > 0 (i.e. they actually contain the product type keyword).
            # If NO candidates matched the keyword, return empty — the product type
            # doesn't exist in this catalog segment, so returning random items is wrong.
            if validation_decisions is None:
                logger.warning("⚠️  LLM VALIDATOR OFFLINE - Applying keyword-based fallback")
                keyword_matched = [p for p in ranked_products if p.get('keyword_score', 0) > 0]
                if keyword_matched:
                    logger.info(f"✅ Keyword fallback: {len(keyword_matched)} products matched keyword '{product_type}'")
                    return keyword_matched[:top_k]
                else:
                    logger.error(f"❌ No products matched keyword '{product_type}'. Returning empty.")
                    return []
                
            # Create lookup map for decisions
            decisions_map = {str(d.get("id")): d for d in validation_decisions}
            
            # Log detailed diagnostics
            logger.info("📋 VALIDATION DECISIONS:")
            for p in ranked_products:
                pid = str(p['product_id'])
                d_info = decisions_map.get(pid, {"decision": "NOT_RELEVANT", "confidence": 0.0, "reason": "No decision"})
                decision = d_info.get('decision')
                conf = d_info.get('confidence')
                reason = d_info.get('reason')
                logger.info(f"   ID={pid} | {p['name']}")
                logger.info(f"      Decision: {decision} | Confidence: {conf:.2f} | Reason: {reason}")
            
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
                    
                # Update final score: 0.7 * hybrid_score + 0.3 * validation_confidence
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
            
            logger.info("=" * 80)
            logger.info(f"✅ VALIDATION SUMMARY:")
            logger.info(f"   RELEVANT: {len(relevant_products)}")
            logger.info(f"   RELATED: {len(related_products)}")
            logger.info(f"   NOT_RELEVANT: {len(ranked_products) - len(relevant_products) - len(related_products)}")
            logger.info("=" * 80)
            
            logger.info(f"<<< EXITING LLM VALIDATION")
            
            # Return both lists separately (don't merge them)
            candidates = {
                'relevant': relevant_products[:top_k],
                'related': related_products[:top_k]
            }
        else:
            logger.info("⏭️  LLM VALIDATION SKIPPED (no specific product type detected)")
            logger.info(f"<<< EXITING LLM VALIDATION")
            # No validation performed - return all ranked products as 'relevant'
            candidates = {
                'relevant': ranked_products[:top_k],
                'related': []
            }
        
        # Final result logging
        logger.info(">>> ENTERING RESPONSE FORMATTING")
        logger.info("🎯" + "=" * 79)
        logger.info(f"🎯 FINAL SEARCH RESULTS")
        
        if isinstance(candidates, dict):
            relevant = candidates.get('relevant', [])
            related = candidates.get('related', [])
            logger.info(f"   RELEVANT products: {len(relevant)}")
            logger.info(f"   RELATED products: {len(related)}")
            
            if relevant:
                logger.info("   RELEVANT product list:")
                for idx, c in enumerate(relevant, 1):
                    logger.info(f"      {idx}. ID={c['product_id']} | {c['name']} | Price=₹{c.get('price')}")
            else:
                logger.warning("   ⚠️  NO RELEVANT PRODUCTS")
            
            if related:
                logger.info("   RELATED product list:")
                for idx, c in enumerate(related, 1):
                    logger.info(f"      {idx}. ID={c['product_id']} | {c['name']} | Price=₹{c.get('price')}")
        else:
            # Fallback for old format (shouldn't happen with current code)
            logger.info(f"   Total products returned: {len(candidates)}")
            if candidates:
                logger.info("   Final product list:")
                for idx, c in enumerate(candidates, 1):
                    logger.info(f"      {idx}. ID={c['product_id']} | {c['name']} | Price=₹{c.get('price')}")
        
        logger.info("=" * 80)
        logger.info(f"<<< EXITING RESPONSE FORMATTING")
        logger.info(f"<<< EXITING search() METHOD")
        
        # Handle different return formats for backward compatibility
        if return_format == 'flat':
            # For backward compatibility (Task Tool): return only RELEVANT products as flat list
            if isinstance(candidates, dict):
                relevant = candidates.get('relevant', [])
                logger.info(f"   [COMPAT] Returning flat list: {len(relevant)} RELEVANT products")
                return relevant
            else:
                # Shouldn't happen, but handle gracefully
                return candidates
        else:
            # Default: return dict format for external API
            return candidates
