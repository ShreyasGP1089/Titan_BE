"""
Compare Tool
Retrieves products for comparison
"""
import logging
from typing import List, Dict
from psycopg2.extras import RealDictCursor
from models.schemas import CompareArguments, CompareResponse, Product
from database import connect_db, release_connection
from services.hybrid_search import convert_decimals

logger = logging.getLogger(__name__)


class CompareTool:
    """Tool for executing compare intent"""
    
    def execute(self, arguments: CompareArguments) -> CompareResponse:
        """
        Execute compare request.
        
        Resolves natural language product names to IDs first, then retrieves products.
        
        Args:
            arguments: CompareArguments with product references (IDs or names)
        
        Returns:
            CompareResponse with resolved products
        """
        product_refs = arguments.products
        
        logger.info("=" * 80)
        logger.info("COMPARE TOOL EXECUTION")
        logger.info(f"Extracted product references: {product_refs}")
        logger.info("=" * 80)
        
        if len(product_refs) < 2:
            raise ValueError("At least 2 products required for comparison")
        
        # Resolve all references
        resolved_products = []
        resolved_ids = []
        for ref in product_refs:
            resolved_p = self._resolve_product(ref)
            resolved_products.append(resolved_p)
            resolved_ids.append(resolved_p['product_id'])
            
        logger.info(f"Successfully resolved all products -> IDs: {resolved_ids}")
        
        # Convert to Product objects
        product_objects = [Product(**p) for p in resolved_products]
        
        response = CompareResponse(
            products=product_objects
        )
        
        logger.info(f"Compare returned {len(product_objects)} products")
        
        return response
        
    def _resolve_product(self, p_ref: str) -> Dict:
        """
        Resolve a product reference (ID or name) to a product dictionary.
        
        Resolution rules:
        - Exact ID match preferred.
        - Exact name match preferred.
        - Otherwise use highest-ranked hybrid search result.
        - Confidence threshold of 0.60 required.
        - If confidence is too low, raise ValueError with suggestions.
        """
        p_ref_clean = p_ref.strip()
        if not p_ref_clean:
            raise ValueError("Empty product reference")
            
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # 1. Exact ID match check
            cur.execute("SELECT * FROM products WHERE product_id = %s", (p_ref_clean,))
            row = cur.fetchone()
            if row:
                product = convert_decimals(dict(row))
                logger.info(f"Resolved reference '{p_ref}':")
                logger.info(f"  Decision: Resolved via direct product ID match")
                logger.info(f"  Resolved ID: {product['product_id']}")
                logger.info(f"  Confidence: 1.0")
                return product
                
            # 2. Exact name match check (case-insensitive)
            cur.execute("SELECT * FROM products WHERE LOWER(name) = LOWER(%s) LIMIT 1", (p_ref_clean,))
            row = cur.fetchone()
            if row:
                product = convert_decimals(dict(row))
                logger.info(f"Resolved reference '{p_ref}':")
                logger.info(f"  Decision: Resolved via exact name match")
                logger.info(f"  Resolved ID: {product['product_id']}")
                logger.info(f"  Confidence: 1.0")
                return product
                
            # 3. Hybrid search fallback
            # Extract keywords from the name reference
            words = [w.strip() for w in p_ref_clean.lower().split() if w.strip()]
            if not words:
                raise ValueError(f"Could not extract keywords from product reference: '{p_ref}'")
                
            # Search candidates in the database using tsquery on name
            # Ignore single-character tokens in query text to prevent filtering out correct matches
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
                # Ignore single-character tokens (like 'g')
                clean_words = [w for w in words if len(w) > 1]
                if not clean_words:
                    clean_words = words # fallback if all are single-char
                for w in clean_words[:5]:
                    conditions.append("name ILIKE %s")
                    params.append(f"%{w}%")
                if conditions:
                    # Sort by rating and review count to prioritize high-quality candidates
                    query = f"SELECT * FROM products WHERE {' OR '.join(conditions)} ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST LIMIT 30;"
                    cur.execute(query, tuple(params))
                    candidates = [convert_decimals(dict(r)) for r in cur.fetchall()]
                    
            if not candidates:
                logger.info(f"Resolved reference '{p_ref}':")
                logger.info(f"  Decision: RESOLUTION FAILED (No candidates found)")
                raise ValueError(f"Could not resolve product '{p_ref}' confidently. No similar products found.")
                
            # Score candidates using HybridSearchService ranking
            from services.hybrid_search import HybridSearchService
            search_service = HybridSearchService()
            
            # Get semantic scores
            semantic_scores = search_service.semantic_search(query_text=p_ref_clean, candidate_products=candidates)
            
            scored_candidates = []
            for p in candidates:
                pid = p['product_id']
                kw_score = search_service.calculate_keyword_score(p, words)
                sem_score = semantic_scores.get(pid, 0.0)
                final_score = (sem_score * 0.6) + (kw_score * 0.4)
                scored_candidates.append((p, final_score))
                
            # Sort scored candidates by final_score descending
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            
            best_candidate, confidence = scored_candidates[0]
            
            # SLM Bypass Condition: if hybrid search confidence is extremely high (>= 0.90)
            if confidence >= 0.90:
                logger.info(f"Resolved reference '{p_ref}':")
                logger.info(f"  Decision: Resolved via hybrid search fallback (Bypassed SLM - High Confidence)")
                logger.info(f"  Resolved ID: {best_candidate['product_id']}")
                logger.info(f"  Confidence: {confidence:.4f}")
                return best_candidate
                
            # Otherwise: Run SLM Validation to ensure we don't match unrelated products
            from services.validation_service import ProductValidationService
            validation_service = ProductValidationService()
            
            # Batch validate the top 10 candidates
            candidates_to_validate = [item[0] for item in scored_candidates[:10]]
            validation_decisions = validation_service.validate_compare_candidates(
                query_product_name=p_ref_clean,
                candidates=candidates_to_validate
            )
            
            # Safe Fallback: if SLM validation service is offline or fails, use standard threshold (>= 0.60)
            if validation_decisions is None:
                logger.warning("SLM compare validation service failed or offline. Falling back to default hybrid threshold (0.60).")
                if confidence >= 0.60:
                    logger.info(f"Resolved reference '{p_ref}':")
                    logger.info(f"  Decision: Resolved via hybrid search fallback (SLM Offline)")
                    logger.info(f"  Resolved ID: {best_candidate['product_id']}")
                    logger.info(f"  Confidence: {confidence:.4f}")
                    return best_candidate
                else:
                    logger.info(f"Resolved reference '{p_ref}':")
                    logger.info(f"  Decision: RESOLUTION FAILED (SLM Offline, confidence {confidence:.4f} < 0.60)")
                    suggestions = [p[0]['name'] for p in scored_candidates[:3]]
                    raise ValueError(
                        f"Could not resolve product '{p_ref}' confidently. "
                        f"Did you mean: {', '.join(suggestions)}?"
                    )
            
            # Create a decision lookup map
            decisions_map = {str(d.get("id")): d for d in validation_decisions}
            
            # Log all SLM compare validation decisions for diagnostics
            logger.info("=" * 80)
            logger.info(f"SLM COMPARE VALIDATION FOR: '{p_ref}'")
            logger.info("=" * 80)
            for p, score in scored_candidates[:10]:
                pid = str(p['product_id'])
                d_info = decisions_map.get(pid, {"decision": "NO_MATCH", "confidence": 0.0, "reason": "No decision from SLM"})
                logger.info(f"Candidate: {p['name']} [id={pid}]")
                logger.info(f"  Hybrid Score: {score:.4f}")
                logger.info(f"  SLM Decision: {d_info.get('decision')}")
                logger.info(f"  SLM Confidence: {d_info.get('confidence')}")
                logger.info(f"  SLM Reason: {d_info.get('reason')}")
                logger.info("-" * 40)
            logger.info("=" * 80)
            
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
                logger.info(f"Resolved reference '{p_ref}':")
                logger.info(f"  Decision: Resolved via SLM validation ({resolved_decision})")
                logger.info(f"  Resolved ID: {resolved_candidate['product_id']}")
                logger.info(f"  SLM Confidence: {resolved_slm_confidence:.4f}")
                logger.info(f"  Reason: {resolved_reason}")
                return resolved_candidate
            else:
                logger.info(f"Resolved reference '{p_ref}':")
                logger.info(f"  Decision: RESOLUTION FAILED (No candidates passed SLM matching thresholds)")
                # Suggest top candidates based on hybrid score
                suggestions = [p[0]['name'] for p in scored_candidates[:3]]
                raise ValueError(
                    f"Could not resolve product '{p_ref}' confidently. "
                    f"Did you mean: {', '.join(suggestions)}?"
                )
        finally:
            cur.close()
            release_connection(conn)
    
    def _get_products_by_ids(self, product_ids: List[str]) -> List[Dict]:
        """
        Retrieve products by IDs from database.
        
        Args:
            product_ids: List of product IDs
        
        Returns:
            List of product dictionaries
        """
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Build query with parameterized IN clause
            placeholders = ','.join(['%s'] * len(product_ids))
            query = f"""
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
                WHERE product_id IN ({placeholders})
                ORDER BY ARRAY_POSITION(%s::text[], product_id);
            """
            
            # Execute query (maintain order of input IDs)
            cur.execute(query, tuple(product_ids) + (product_ids,))
            results = cur.fetchall()
            
            logger.info(f"Found {len(results)} products for comparison")
            
            return [convert_decimals(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Product retrieval error: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)
