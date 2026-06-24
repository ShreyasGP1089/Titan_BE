import logging
import requests
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Default model server URL
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:8000")

class ProductValidationService:
    """Service to interact with the SLM for product relevance validation"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 90):
        self.base_url = base_url or LOCAL_MODEL_URL
        self.timeout = timeout
        logger.info(f"ProductValidationService initialized: {self.base_url}")
        
    def validate_products(self, requested_product_type: str, candidates: List[Dict]) -> Optional[List[Dict]]:
        """
        Validate candidates against a requested product type using the SLM.
        
        Args:
            requested_product_type: E.g. "bottle", "helmet", "shoes", etc.
            candidates: List of product dictionaries with keys 'product_id', 'name', 'description'.
            
        Returns:
            List of validation results, e.g.:
            [
                {
                    "id": "123",
                    "decision": "RELEVANT" | "RELATED" | "NOT_RELEVANT",
                    "confidence": 0.98,
                    "reason": "..."
                }
            ]
            Or None if validation service is unavailable (e.g. offline).
        """
        if not candidates:
            return []
            
        payload = {
            "requested_product_type": requested_product_type,
            "candidates": [
                {
                    "id": str(c.get("product_id")),
                    "name": c.get("name", ""),
                    "description": c.get("description") or ""
                }
                for c in candidates
            ]
        }
        
        url = f"{self.base_url}/validate-products"
        logger.info(f"Calling SLM validation at {url} for type '{requested_product_type}' with {len(candidates)} candidates")
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"SLM validator error: status {response.status_code}, response: {response.text}")
                return None
                
            data = response.json()
            validated_list = data.get("validated", [])
            logger.info(f"✓ SLM validator returned {len(validated_list)} decisions")
            return validated_list
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ SLM validation service unavailable (RequestException: {e}). Fallback to standard search ranking.")
            return None

    def validate_compare_candidates(self, query_product_name: str, candidates: List[Dict]) -> Optional[List[Dict]]:
        """
        Validate candidates against a query product name using the SLM.
        
        Args:
            query_product_name: The requested product name query.
            candidates: List of product dictionaries with keys 'product_id', 'name', 'description'.
            
        Returns:
            List of validation results, e.g.:
            [
                {
                    "id": "123",
                    "decision": "MATCH" | "PARTIAL_MATCH" | "NO_MATCH",
                    "confidence": 0.98,
                    "reason": "..."
                }
            ]
            Or None if validation service is unavailable (e.g. offline).
        """
        if not candidates:
            return []
            
        payload = {
            "query_product_name": query_product_name,
            "candidates": [
                {
                    "id": str(c.get("product_id")),
                    "name": c.get("name", ""),
                    "description": c.get("description") or ""
                }
                for c in candidates
            ]
        }
        
        url = f"{self.base_url}/validate-compare-candidates"
        logger.info(f"Calling SLM compare validation at {url} for query '{query_product_name}' with {len(candidates)} candidates")
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"SLM compare validator error: status {response.status_code}, response: {response.text}")
                return None
                
            data = response.json()
            validated_list = data.get("validated", [])
            logger.info(f"✓ SLM compare validator returned {len(validated_list)} decisions")
            return validated_list
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ SLM compare validation service unavailable (RequestException: {e}). Fallback to standard compare resolution ranking.")
            return None

    def generate_alternative_search(self, source_product: Dict, user_query: str) -> Optional[Dict]:
        """
        Generate alternative search criteria and constraints using the SLM.
        """
        payload = {
            "source_product": {
                "name": source_product.get("name", ""),
                "sport": source_product.get("sport", ""),
                "category_level_1": source_product.get("category_level_1", ""),
                "description": source_product.get("description") or ""
            },
            "user_query": user_query
        }
        
        url = f"{self.base_url}/generate-alternative-search"
        logger.info(f"Calling SLM generate-alternative-search for product: '{source_product.get('name')}' with query '{user_query}'")
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"SLM generate-alternative-search error: status {response.status_code}, response: {response.text}")
                return None
                
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ SLM alternative generation service unavailable: {e}. Falling back to default metadata-based search.")
            return None

    def validate_substitute_candidates(
        self,
        source_product_name: str,
        source_product_type: str,
        source_sport: str,
        candidates: List[Dict]
    ) -> Optional[List[Dict]]:
        """
        Validate candidates as genuine substitutes for the source product.
        
        Args:
            source_product_name: Name of the source product
            source_product_type: Core product type (e.g., "football", "bottle")
            source_sport: Sport category
            candidates: List of product dicts
            
        Returns:
            List of validation results with decisions:
            ALTERNATIVE / RELATED / NOT_ALTERNATIVE
            Or None if service is unavailable.
        """
        if not candidates:
            return []
            
        payload = {
            "source_product_name": source_product_name,
            "source_product_type": source_product_type,
            "source_sport": source_sport or "",
            "candidates": [
                {
                    "id": str(c.get("product_id")),
                    "name": c.get("name", ""),
                    "description": c.get("description") or ""
                }
                for c in candidates
            ]
        }
        
        url = f"{self.base_url}/validate-substitute-candidates"
        logger.info(f"Calling SLM substitute validation at {url} for '{source_product_name}' (type: {source_product_type}) with {len(candidates)} candidates")
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"SLM substitute validator error: status {response.status_code}, response: {response.text}")
                return None
                
            data = response.json()
            validated_list = data.get("validated", [])
            logger.info(f"✓ SLM substitute validator returned {len(validated_list)} decisions")
            return validated_list
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ SLM substitute validation service unavailable: {e}. Skipping substitute filter.")
            return None

