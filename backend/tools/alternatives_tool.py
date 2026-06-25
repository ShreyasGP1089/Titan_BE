"""
Alternatives Tool
Finds alternative products similar to a given product with constraint awareness (V2)
"""
import logging
import re
from typing import List, Dict, Optional
from psycopg2.extras import RealDictCursor
from models.schemas import AlternativesArguments, AlternativesResponse, Product
from database import connect_db, release_connection
from services.hybrid_search import HybridSearchService, convert_decimals
from services.validation_service import ProductValidationService

logger = logging.getLogger(__name__)


class AlternativesTool:
    """Tool for finding product alternatives with constraints (V2)"""
    
    def execute(self, arguments: AlternativesArguments) -> AlternativesResponse:
        """
        Execute alternatives request.
        
        Flow:
            1. Resolve product by name or ID.
            2. Call SLM to extract search criteria and user constraints.
            3. Query candidates using HybridSearchService.
            4. Filter candidates dynamically by constraints (brand, rating, lower price, etc.).
            5. Re-rank based on constraints, validation, and hybrid search scores.
            6. Return top candidates.
        """
        product_ref = arguments.product
        user_query = arguments.query or f"Show alternatives to {product_ref}"
        
        logger.info("=" * 80)
        logger.info("ALTERNATIVES TOOL EXECUTION (V2)")
        logger.info(f"Product Ref: {product_ref}")
        logger.info(f"User Query: {user_query}")
        logger.info("=" * 80)
        
        # 1. Resolve source product
        source_product = self._resolve_product(product_ref)
        source_product_id = source_product['product_id']
        
        logger.info(f"Resolved source product: '{source_product['name']}' [id={source_product_id}]")
        
        # 2. Call SLM to generate search criteria and constraints
        validation_service = ProductValidationService()
        criteria = validation_service.generate_alternative_search(source_product, user_query)
        
        search_service = HybridSearchService()
        candidates = []
        use_fallback = False
        
        if criteria:
            # Extract criteria
            sport = criteria.get("sport") or source_product.get("sport")
            category_level_1 = criteria.get("category_level_1") or source_product.get("category_level_1")
            keywords = criteria.get("keywords") or []
            must_contain = criteria.get("must_contain") or []
            price_range_factor = float(criteria.get("price_range_factor") or 2.0)
            constraints = criteria.get("constraints") or {}
            
            logger.info("Generated Criteria from SLM:")
            logger.info(f"  Sport: {sport}")
            logger.info(f"  Category L1: {category_level_1}")
            logger.info(f"  Keywords: {keywords}")
            logger.info(f"  Must Contain: {must_contain}")
            logger.info(f"  Price Factor: {price_range_factor}")
            logger.info(f"  Constraints: {constraints}")
            
            # Calculate price bounds
            source_price = float(source_product.get("price") or 0.0)
            price_min = source_price / price_range_factor
            price_max = source_price * price_range_factor
            
            # If user specified a budget limit, override the max price bound
            price_limit = price_max
            if constraints.get("budget_limit") is not None:
                price_limit = min(price_max, float(constraints["budget_limit"]))
                logger.info(f"Budget constraint active: limit=₹{price_limit}")
            
            # Retrieve candidates via HybridSearchService
            candidates = search_service.search(
                sport=sport,
                category_level_1=category_level_1,
                keywords=keywords,
                price_limit=price_limit,
                top_k=30
            )
            
            # Exclude original product
            candidates = [c for c in candidates if c["product_id"] != source_product_id]
            
            # Filter: must_contain check
            # Split multi-word terms into individual words for robust matching
            # (handles inconsistent spacing in product names, e.g. "Water  Bottle")
            if must_contain:
                must_words = set()
                for term in must_contain:
                    for word in term.lower().split():
                        if len(word) > 1:
                            must_words.add(word)
                if must_words:
                    candidates = [
                        c for c in candidates
                        if all(word in (c.get("name") or "").lower() for word in must_words)
                    ]
                    logger.info(f"Filter must_contain words {must_words} applied: {len(candidates)} candidates remaining")
                
            # Filter: price_min bound
            # Skip price floor when user explicitly asks for cheaper alternatives
            if constraints.get("lower_price"):
                logger.info(f"Skipping price_min filter: user requested lower_price alternatives")
            else:
                candidates = [c for c in candidates if float(c.get("price") or 0.0) >= price_min]
                logger.info(f"Filter price_min >= {price_min:.2f} applied: {len(candidates)} candidates remaining")
            
            # Filter: higher_rating
            if constraints.get("higher_rating"):
                source_rating = float(source_product.get("rating") or 0.0)
                candidates = [
                    c for c in candidates
                    if c.get("rating") is not None and float(c.get("rating") or 0.0) > source_rating
                ]
                logger.info(f"Filter higher_rating > {source_rating} applied: {len(candidates)} candidates remaining")
                
            # Filter: lower_price
            # Guard: if budget_limit is set and exceeds source price, the user is
            # asking for "under X" (budget cap), not "cheaper than source".
            # The SLM sometimes conflates the two — skip lower_price in that case.
            budget_limit_val = constraints.get("budget_limit")
            apply_lower_price = constraints.get("lower_price")
            if apply_lower_price and budget_limit_val is not None and float(budget_limit_val) > source_price:
                logger.info(f"Skipping lower_price filter: budget_limit ({budget_limit_val}) > source_price ({source_price}) indicates a budget cap, not a 'cheaper' request")
                apply_lower_price = False
                
            if apply_lower_price:
                candidates = [
                    c for c in candidates
                    if float(c.get("price") or 0.0) < source_price
                ]
                logger.info(f"Filter lower_price < {source_price} applied: {len(candidates)} candidates remaining")
                
            # Filter: different_brand
            if constraints.get("different_brand"):
                source_brand = (source_product.get("brand") or "").strip().lower()
                candidates = [
                    c for c in candidates
                    if (c.get("brand") or "").strip().lower() != source_brand
                ]
                logger.info(f"Filter different_brand != '{source_brand}' applied: {len(candidates)} candidates remaining")
                
            # Filter: same_brand
            if constraints.get("same_brand"):
                source_brand = (source_product.get("brand") or "").strip().lower()
                candidates = [
                    c for c in candidates
                    if (c.get("brand") or "").strip().lower() == source_brand
                ]
                logger.info(f"Filter same_brand == '{source_brand}' applied: {len(candidates)} candidates remaining")
                
            # Filter: more_reviews
            if constraints.get("more_reviews"):
                source_reviews = int(source_product.get("review_count") or 0)
                candidates = [
                    c for c in candidates
                    if c.get("review_count") is not None and int(c.get("review_count") or 0) > source_reviews
                ]
                logger.info(f"Filter more_reviews > {source_reviews} applied: {len(candidates)} candidates remaining")
                
            # Rank candidates
            if candidates:
                # Compute normalization bounds
                ratings = [float(c.get("rating") or 0.0) for c in candidates]
                reviews = [int(c.get("review_count") or 0) for c in candidates]
                prices = [float(c.get("price") or 0.0) for c in candidates]
                
                max_rating, min_rating = max(ratings), min(ratings)
                max_reviews, min_reviews = max(reviews), min(reviews)
                max_price, min_price = max(prices), min(prices)
                
                ranked_candidates = []
                for c in candidates:
                    rating = float(c.get("rating") or 0.0)
                    review_count = int(c.get("review_count") or 0)
                    price = float(c.get("price") or 0.0)
                    
                    # Normalize helper
                    def norm(val, val_min, val_max):
                        return (val - val_min) / (val_max - val_min) if val_max > val_min else 1.0
                        
                    norm_rating = norm(rating, min_rating, max_rating)
                    norm_reviews = norm(review_count, min_reviews, max_reviews)
                    norm_price = norm(price, min_price, max_price)
                    
                    # Premium score: higher price, higher rating, higher reviews
                    premium_score = norm_rating * 0.4 + norm_reviews * 0.2 + norm_price * 0.4
                    
                    if constraints.get("premium"):
                        constraint_score = premium_score
                    else:
                        constraint_score = 0.5  # Neutral
                        
                    hybrid_score = float(c.get("final_score") or 0.5)
                    validation_score = float(c.get("validation_confidence") or 0.5)
                    
                    # Re-rank formula: 60% hybrid, 20% validation, 20% constraints
                    reranked_score = round((hybrid_score * 0.6) + (validation_score * 0.2) + (constraint_score * 0.2), 4)
                    
                    c_copy = c.copy()
                    c_copy["final_score"] = reranked_score
                    c_copy["validation_confidence"] = validation_score
                    ranked_candidates.append(c_copy)
                    
                # Sort descending
                ranked_candidates.sort(key=lambda x: x["final_score"], reverse=True)
                candidates = ranked_candidates
        else:
            use_fallback = True
            logger.warning("SLM generation failed or offline. Using metadata-based fallback.")
            
        # Only use fallback when SLM actually failed.
        # When SLM succeeded but constraints filtered everything, return empty results
        # (honoring the user's constraints rather than ignoring them).
        if use_fallback:
            # Fallback logic: Use source product metadata directly
            sport = source_product.get("sport")
            category_level_1 = source_product.get("category_level_1")
            
            # Clean tokens from source name for keywords
            name_clean = re.sub(r'[^a-zA-Z0-9\s]', '', source_product.get("name", "").lower())
            keywords = [w.strip() for w in name_clean.split() if len(w.strip()) > 1]
            
            logger.info("Executing Metadata-Based Fallback:")
            logger.info(f"  Sport: {sport}")
            logger.info(f"  Category L1: {category_level_1}")
            logger.info(f"  Keywords: {keywords}")
            
            candidates = search_service.search(
                sport=sport,
                category_level_1=category_level_1,
                keywords=keywords,
                top_k=10
            )
            candidates = [c for c in candidates if c["product_id"] != source_product_id]
        elif not candidates:
            logger.info("SLM succeeded but constraints filtered all candidates. Returning empty results (no matching alternatives found).")
        
        # ================================================================
        # POST-RETRIEVAL SLM SUBSTITUTE VALIDATION
        # Validate top candidates are genuine substitutes, not just related
        # ================================================================
        if candidates:
            product_type = ""
            if criteria:
                product_type = criteria.get("product_type", "")
            if not product_type:
                # Infer from source product name
                name_words = source_product.get("name", "").lower().split()
                product_type = name_words[0] if name_words else ""
            
            source_sport = source_product.get("sport", "")
            
            # Validate top 20 candidates
            candidates_to_validate = candidates[:20]
            substitute_decisions = validation_service.validate_substitute_candidates(
                source_product_name=source_product.get("name", ""),
                source_product_type=product_type,
                source_sport=source_sport,
                candidates=candidates_to_validate
            )
            
            if substitute_decisions is not None:
                # Build decision lookup
                decisions_map = {str(d.get("id")): d for d in substitute_decisions}
                
                # Log all decisions for diagnostics
                logger.info("=" * 80)
                logger.info(f"SLM SUBSTITUTE VALIDATION FOR: '{source_product.get('name')}'")
                logger.info("=" * 80)
                
                validated_candidates = []
                for c in candidates_to_validate:
                    pid = str(c['product_id'])
                    d_info = decisions_map.get(pid, {})
                    decision = d_info.get("decision", "NOT_ALTERNATIVE").upper()
                    conf = float(d_info.get("confidence", 0.0))
                    reason = d_info.get("reason", "No decision from SLM")
                    
                    logger.info(f"  {c['name']} [id={pid}]")
                    logger.info(f"    Decision: {decision} | Confidence: {conf} | Reason: {reason}")
                    
                    if decision == "ALTERNATIVE":
                        validated_candidates.append(c)
                
                logger.info("=" * 80)
                logger.info(f"Substitute validation: {len(validated_candidates)}/{len(candidates_to_validate)} candidates passed as ALTERNATIVE")
                
                # Use validated candidates if we got any, otherwise keep original
                # (graceful degradation: if SLM rejects everything, keep search results)
                if validated_candidates:
                    candidates = validated_candidates
                else:
                    logger.warning("SLM rejected all candidates as non-substitutes. Keeping original search results as fallback.")
            else:
                logger.warning("SLM substitute validation unavailable. Skipping substitute filter.")
            
        # Convert to Product objects
        product_objects = [Product(**c) for c in candidates[:10]]
        
        response = AlternativesResponse(
            source_product=Product(**source_product),
            products=product_objects,
            total=len(product_objects)
        )
        
        logger.info(f"V2 Alternatives returned {len(product_objects)} products")
        return response
        
    def _resolve_product(self, p_ref: str) -> Dict:
        """
        Resolve a product reference (ID or name) to a product dictionary.
        Exactly matches compare_tool.py logic.
        """
        p_ref_clean = p_ref.strip()
        if not p_ref_clean:
            raise ValueError("Empty product reference")
            
        # Clean constraints from the product reference
        # Suffix constraint patterns to strip (case-insensitive, matched at the end of the string)
        patterns = [
            # Brands
            r'\s+(?:from|by|of)\s+(?:the\s+)?(?:same|another|different|other|any)\s+brands?$',
            # Rating / Reviews / Price
            r'\s+with\s+(?:a\s+)?(?:higher|better|lower|more|premium)\s+(?:rating|reviews?|price|popularity)$',
            r'\s+with\s+more\s+reviews?$',
            r'\s+with\s+higher\s+reviews?$',
            r'\s+(?:that\s+are\s+)?highly\s+rated$',
            # Price numbers/budget
            r'\s+(?:under|below|above|over|for|at|limit)\s+(?:₹|rs\.?|inr)?\s*\d+$',
            r'\s+under\s+budget$',
            # Adjectives/Comparison suffixes
            r'\s+(?:that\s+are\s+)?(?:cheaper|cheap|premium|expensive|better|similar)$',
        ]
        
        changed = True
        while changed:
            changed = False
            for pattern in patterns:
                new_ref = re.sub(pattern, '', p_ref_clean, flags=re.IGNORECASE).strip()
                if new_ref != p_ref_clean:
                    p_ref_clean = new_ref
                    changed = True
                    break

        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # 1. Exact ID match check
            cur.execute("SELECT * FROM products WHERE product_id = %s", (p_ref_clean,))
            row = cur.fetchone()
            if row:
                product = convert_decimals(dict(row))
                logger.info(f"Resolved reference '{p_ref}': Resolved via direct product ID match")
                return product
                
            # 2. Exact name match check (case-insensitive)
            cur.execute("SELECT * FROM products WHERE LOWER(name) = LOWER(%s) LIMIT 1", (p_ref_clean,))
            row = cur.fetchone()
            if row:
                product = convert_decimals(dict(row))
                logger.info(f"Resolved reference '{p_ref}': Resolved via exact name match")
                return product
                
            # 3. Hybrid search fallback
            words = [w.strip() for w in p_ref_clean.lower().split() if w.strip()]
            if not words:
                raise ValueError(f"Could not extract keywords from product reference: '{p_ref}'")
                
            clean_query_words = [w.strip() for w in p_ref_clean.split() if len(w.strip()) > 1]
            clean_query = " ".join(clean_query_words) if clean_query_words else p_ref_clean
            
            query = """
                SELECT * FROM products
                WHERE to_tsvector('english', COALESCE(name, '')) @@ plainto_tsquery('english', %s)
                LIMIT 30;
            """
            cur.execute(query, (clean_query,))
            candidates = [convert_decimals(dict(r)) for r in cur.fetchall()]
            
            # Relaxed fallback search: if tsquery returns nothing, do ILIKE on name words
            if not candidates:
                conditions = []
                params = []
                clean_words = [w for w in words if len(w) > 1]
                if not clean_words:
                    clean_words = words
                for w in clean_words[:5]:
                    conditions.append("name ILIKE %s")
                    params.append(f"%{w}%")
                if conditions:
                    query = f"SELECT * FROM products WHERE {' OR '.join(conditions)} ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST LIMIT 30;"
                    cur.execute(query, tuple(params))
                    candidates = [convert_decimals(dict(r)) for r in cur.fetchall()]
                    
            if not candidates:
                logger.info(f"Resolved reference '{p_ref}': RESOLUTION FAILED (No candidates found)")
                raise ValueError(f"Could not resolve product '{p_ref}' confidently. No similar products found.")
                
            # Score candidates using HybridSearchService ranking
            search_service = HybridSearchService()
            semantic_scores = search_service.semantic_search(query_text=p_ref_clean, candidate_products=candidates)
            
            scored_candidates = []
            for p in candidates:
                pid = p['product_id']
                kw_score = search_service.calculate_keyword_score(p, words)
                sem_score = semantic_scores.get(pid, 0.0)
                final_score = (sem_score * 0.6) + (kw_score * 0.4)
                scored_candidates.append((p, final_score))
                
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            best_candidate, confidence = scored_candidates[0]
            
            # SLM Bypass Condition: if hybrid search confidence is extremely high (>= 0.90)
            if confidence >= 0.90:
                logger.info(f"Resolved reference '{p_ref}': Resolved via hybrid search fallback (Bypassed SLM - High Confidence)")
                return best_candidate
                
            # Otherwise: Run SLM Validation to ensure we don't match unrelated products
            validation_service = ProductValidationService()
            candidates_to_validate = [item[0] for item in scored_candidates[:10]]
            validation_decisions = validation_service.validate_compare_candidates(
                query_product_name=p_ref_clean,
                candidates=candidates_to_validate
            )
            
            # Safe Fallback: if SLM validation service is offline or fails, use standard threshold (>= 0.60)
            if validation_decisions is None:
                logger.warning("SLM compare validation service failed or offline. Falling back to default hybrid threshold (0.60).")
                if confidence >= 0.60:
                    logger.info(f"Resolved reference '{p_ref}': Resolved via hybrid search fallback (SLM Offline)")
                    return best_candidate
                else:
                    suggestions = [p[0]['name'] for p in scored_candidates[:3]]
                    raise ValueError(
                        f"Could not resolve product '{p_ref}' confidently. Did you mean: {', '.join(suggestions)}?"
                    )
            
            # Create a decision lookup map
            decisions_map = {str(d.get("id")): d for d in validation_decisions}
            
            # Find the best candidate satisfying:
            # - MATCH with SLM confidence >= 0.80
            # - PARTIAL_MATCH with SLM confidence >= 0.85
            resolved_candidate = None
            resolved_reason = ""
            resolved_decision = ""
            resolved_slm_confidence = 0.0
            
            for p, score in scored_candidates[:10]:
                pid = str(p['product_id'])
                d_info = decisions_map.get(pid)
                if not d_info:
                    continue
                    
                decision = d_info.get("decision", "NO_MATCH").upper()
                slm_conf = float(d_info.get("confidence", 0.0))
                
                is_valid = False
                if decision == "MATCH" and slm_conf >= 0.80:
                    is_valid = True
                elif decision == "PARTIAL_MATCH" and slm_conf >= 0.85:
                    is_valid = True
                    
                if is_valid:
                    resolved_candidate = p
                    resolved_reason = d_info.get("reason", "")
                    resolved_decision = decision
                    resolved_slm_confidence = slm_conf
                    break
                    
            if resolved_candidate:
                logger.info(f"Resolved reference '{p_ref}': Resolved via SLM validation ({resolved_decision})")
                return resolved_candidate
            else:
                logger.info(f"Resolved reference '{p_ref}': RESOLUTION FAILED (No candidates passed SLM matching thresholds)")
                suggestions = [p[0]['name'] for p in scored_candidates[:3]]
                raise ValueError(
                    f"Could not resolve product '{p_ref}' confidently. Did you mean: {', '.join(suggestions)}?"
                )
        finally:
            cur.close()
            release_connection(conn)
