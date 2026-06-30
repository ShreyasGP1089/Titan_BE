"""
Compare Tool
Simple keyword-based SQL matching for product comparison
"""
import logging
import re
import requests
import os
from typing import List, Dict
from psycopg2.extras import RealDictCursor
from models.schemas import CompareArguments, CompareResponse, Product, ComparisonSummary
from database import connect_db, release_connection
from services.hybrid_search import convert_decimals

logger = logging.getLogger(__name__)

# Local model server URL
LOCAL_MODEL_URL = os.getenv('LOCAL_MODEL_URL', 'http://localhost:8000')


class CompareTool:
    """Tool for executing compare intent"""
    
    def execute(self, arguments: CompareArguments) -> CompareResponse:
        """
        Execute compare request using simple keyword-based SQL matching.
        
        Args:
            arguments: CompareArguments with product references
        
        Returns:
            CompareResponse with resolved products and any missing product mentions
        """
        product_refs = arguments.products
        
        logger.info("=" * 80)
        logger.info("COMPARE TOOL EXECUTION")
        logger.info(f"Product mentions: {len(product_refs)}")
        for idx, ref in enumerate(product_refs, 1):
            logger.info(f"  {idx}. \"{ref}\"")
        logger.info("=" * 80)
        
        if len(product_refs) < 2:
            raise ValueError("At least 2 products required for comparison")
        
        # Resolve each product independently
        resolved_products = []
        missing_products = []
        
        for idx, ref in enumerate(product_refs, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"RESOLVING PRODUCT {idx}: \"{ref}\"")
            logger.info(f"{'='*80}")
            
            try:
                resolved_p = self._resolve_product(ref)
                resolved_products.append(resolved_p)
                
                logger.info(f"✓ Resolved to: {resolved_p['name']}")
                logger.info(f"  ID: {resolved_p['product_id']}, Price: ₹{resolved_p['price']}")
                
            except ValueError as e:
                logger.warning(f"✗ Could not resolve: {str(e)}")
                missing_products.append(ref)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"RESOLUTION COMPLETE: {len(resolved_products)} found, {len(missing_products)} missing")
        logger.info(f"{'='*80}\n")
        
        # Build response
        product_objects = [Product(**p) for p in resolved_products]
        
        message = None
        if missing_products:
            if len(missing_products) == len(product_refs):
                message = "None of the requested products could be found in the knowledge base."
            else:
                message = f"{len(missing_products)} of {len(product_refs)} products could not be resolved."
        
        # Generate comparison summary if exactly 2 products resolved
        # NOTE: Temporarily disabled - requires /generate-comparison-summary endpoint
        comparison_summary = None
        # if len(resolved_products) == 2:
        #     try:
        #         comparison_summary = self._generate_comparison_summary(
        #             resolved_products[0],
        #             resolved_products[1]
        #         )
        #     except Exception as e:
        #         logger.warning(f"Failed to generate comparison summary: {e}")
        #         # Continue without comparison summary
        
        return CompareResponse(
            products=product_objects,
            missing_products=missing_products,
            message=message,
            comparison=comparison_summary
        )
    
    def _resolve_product(self, product_mention: str) -> Dict:
        """
        Resolve product using simple keyword-based SQL matching.
        
        1. Normalize query
        2. Extract keywords
        3. SQL WHERE with LIKE for each keyword
        4. Score by overlap
        5. Return best match above threshold
        """
        product_mention = product_mention.strip()
        if not product_mention:
            raise ValueError("Empty product mention")
        
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Check for direct product ID
            cur.execute("SELECT * FROM products WHERE product_id = %s", (product_mention,))
            row = cur.fetchone()
            if row:
                logger.info(f"  ✓ Direct ID match")
                return convert_decimals(dict(row))
            
            # Normalize and extract keywords
            normalized = self._normalize(product_mention)
            keywords = self._extract_keywords(normalized)
            
            logger.info(f"  Normalized: \"{normalized}\"")
            logger.info(f"  Keywords: {keywords}")
            
            if not keywords:
                raise ValueError(f"No keywords extracted from \"{product_mention}\"")
            
            # Build SQL with keyword LIKE conditions
            conditions = []
            params = []
            for keyword in keywords:
                conditions.append("LOWER(name) LIKE %s")
                params.append(f"%{keyword}%")
            
            query = f"""
                SELECT product_id, name, brand, price, mrp, sport,
                       category_level_1, category_level_2, description,
                       image_url, product_url, rating, review_count
                FROM products
                WHERE {' AND '.join(conditions)}
                LIMIT 50
            """
            
            logger.info(f"  Fetching candidates with ALL keywords...")
            cur.execute(query, tuple(params))
            candidates = [convert_decimals(dict(r)) for r in cur.fetchall()]
            logger.info(f"  Found {len(candidates)} candidates")
            
            if not candidates:
                raise ValueError(f"Product not found: \"{product_mention}\"")
            
            # Score by keyword overlap
            scored = []
            for cand in candidates:
                score = self._score(cand['name'], normalized, keywords)
                scored.append((cand, score))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            
            # Log top matches
            logger.info(f"  Top matches:")
            for i, (c, s) in enumerate(scored[:5], 1):
                logger.info(f"    {i}. [{s:.2f}] {c['name']}")
            
            # Return best if above threshold
            best_product, best_score = scored[0]
            
            if best_score < 0.4:
                raise ValueError(f"No good match for \"{product_mention}\" (best score: {best_score:.2f})")
            
            return best_product
            
        finally:
            cur.close()
            release_connection(conn)
    
    def _normalize(self, text: str) -> str:
        """Lowercase, remove punctuation, collapse spaces"""
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        return ' '.join(text.split())
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract significant keywords (no stop words, length > 1)"""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through'
        }
        tokens = text.split()
        return [t for t in tokens if len(t) > 1 and t not in stop_words]
    
    def _score(self, product_name: str, query: str, query_keywords: List[str]) -> float:
        """
        Score match quality.
        
        1.0 = Exact normalized match
        0.9 = Query phrase contained in product
        0.4-0.8 = Keyword overlap ratio
        """
        norm_product = self._normalize(product_name)
        
        # Exact match
        if query == norm_product:
            return 1.0
        
        # Phrase match
        if query in norm_product:
            return 0.9
        
        # Keyword overlap
        product_keywords = set(self._extract_keywords(norm_product))
        query_kw_set = set(query_keywords)
        
        if not query_kw_set:
            return 0.0
        
        overlap = len(query_kw_set & product_keywords) / len(query_kw_set)
        
        # Map overlap to score
        if overlap >= 1.0:
            return 0.8
        elif overlap >= 0.8:
            return 0.7
        elif overlap >= 0.6:
            return 0.6
        elif overlap >= 0.5:
            return 0.5
        else:
            return overlap * 0.8  # Scale proportionally
    
    def _generate_comparison_summary(self, product_1: Dict, product_2: Dict) -> ComparisonSummary:
        """
        Generate AI comparison summary using the local model.
        
        Calls the new /generate-comparison-summary endpoint.
        Only passes structured product information, no raw data.
        
        Args:
            product_1: First product dictionary
            product_2: Second product dictionary
        
        Returns:
            ComparisonSummary object
        """
        logger.info("\n" + "=" * 80)
        logger.info("GENERATING COMPARISON SUMMARY")
        logger.info("=" * 80)
        
        # Prepare structured product data (only what's needed)
        product_1_data = {
            "name": product_1.get('name', ''),
            "brand": product_1.get('brand', ''),
            "category_level_1": product_1.get('category_level_1', ''),
            "category_level_2": product_1.get('category_level_2', ''),
            "sport": product_1.get('sport', ''),
            "price": float(product_1.get('price', 0)),
            "rating": float(product_1.get('rating', 0)) if product_1.get('rating') else None,
            "review_count": int(product_1.get('review_count', 0)) if product_1.get('review_count') else 0,
            "description": product_1.get('description', '')
        }
        
        product_2_data = {
            "name": product_2.get('name', ''),
            "brand": product_2.get('brand', ''),
            "category_level_1": product_2.get('category_level_1', ''),
            "category_level_2": product_2.get('category_level_2', ''),
            "sport": product_2.get('sport', ''),
            "price": float(product_2.get('price', 0)),
            "rating": float(product_2.get('rating', 0)) if product_2.get('rating') else None,
            "review_count": int(product_2.get('review_count', 0)) if product_2.get('review_count') else 0,
            "description": product_2.get('description', '')
        }
        
        logger.info(f"Product 1: {product_1_data['name']}")
        logger.info(f"Product 2: {product_2_data['name']}")
        
        try:
            # Call local model server
            response = requests.post(
                f"{LOCAL_MODEL_URL}/generate-comparison-summary",
                json={
                    "product_1": product_1_data,
                    "product_2": product_2_data
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Comparison summary failed: {response.status_code}")
                raise ValueError(f"Model server returned {response.status_code}")
            
            result = response.json()
            
            logger.info("✓ Comparison summary generated")
            logger.info(f"Summary: {result['summary'][:100]}...")
            logger.info(f"Key differences: {len(result['key_differences'])}")
            logger.info("=" * 80 + "\n")
            
            return ComparisonSummary(
                summary=result['summary'],
                key_differences=result['key_differences'],
                best_for=result['best_for']
            )
            
        except Exception as e:
            logger.error(f"Failed to generate comparison summary: {e}")
            raise
