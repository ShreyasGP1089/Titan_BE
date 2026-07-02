"""
Search Query Parser Service
Converts planner output into optimal search requests for Hybrid Search
"""
import logging
import os
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SearchQueryParserService:
    """Service for parsing product names into optimized search requests"""
    
    def __init__(self):
        """Initialize search query parser service with local model URL"""
        self.base_url = os.getenv("LOCAL_MODEL_URL", "http://localhost:8000")
        logger.info(f"SearchQueryParserService initialized: {self.base_url}")
    
    def parse_search_query(
        self,
        product_name: str,
        sport: Optional[str] = None
    ) -> Dict:
        """
        Parse a product name into an optimal search request.
        
        This is a lightweight parser that determines the best category
        and keywords for searching a specific product.
        
        Responsibility: Convert "Golf Shirt" → optimal search parameters
        Does NOT decide what to search (planner does that)
        Does NOT perform retrieval (Hybrid Search does that)
        
        Args:
            product_name: Product name from planner (e.g., "Golf Shirt")
            sport: Sport name for context
        
        Returns:
            Dict with:
                - sport: str
                - category_level_1: Optional[str]
                - category_level_2: Optional[str]
                - keywords: List[str]
        
        Examples:
            "Golf Shirt" → {"sport": "Golf", "category_level_1": "Apparel", "keywords": ["golf shirt"]}
            "Running Shoes" → {"sport": "Running", "category_level_1": "Footwear", "keywords": ["running shoes"]}
        """
        try:
            payload = {
                "product_name": product_name,
                "sport": sport or ""
            }
            
            url = f"{self.base_url}/parse-search-query"
            logger.info("=" * 80)
            logger.info("SEARCH QUERY PARSER")
            logger.info(f"  Calling: {url}")
            logger.info(f"  Product Name: {product_name}")
            logger.info(f"  Sport: {sport}")
            logger.info("=" * 80)
            
            response = requests.post(
                url,
                json=payload,
                timeout=10  # 10 second timeout (lightweight parser)
            )
            
            if response.status_code != 200:
                logger.error(f"Search query parser returned status {response.status_code}: {response.text}")
                return self._fallback_parse(product_name, sport)
            
            result = response.json()
            
            # Log the parsed search request
            logger.info("=" * 80)
            logger.info("SEARCH QUERY PARSER RESULT")
            logger.info(f"  Product Name: {product_name}")
            logger.info(f"  Generated Search Request:")
            logger.info(f"    sport: {result.get('sport')}")
            logger.info(f"    category_level_1: {result.get('category_level_1')}")
            logger.info(f"    category_level_2: {result.get('category_level_2')}")
            logger.info(f"    keywords: {result.get('keywords')}")
            logger.info("=" * 80)
            
            return result
            
        except requests.Timeout:
            logger.error("Search query parser request timed out")
            return self._fallback_parse(product_name, sport)
        except requests.ConnectionError:
            logger.error("Could not connect to search query parser service")
            return self._fallback_parse(product_name, sport)
        except Exception as e:
            logger.error(f"Error calling search query parser: {e}")
            return self._fallback_parse(product_name, sport)
    
    def _fallback_parse(self, product_name: str, sport: Optional[str]) -> Dict:
        """
        Fallback parser when SLM is unavailable.
        
        Creates a basic search request deterministically.
        """
        logger.warning("Using fallback search query parser")
        
        result = {
            "sport": sport or "Unknown",
            "category_level_1": None,
            "category_level_2": None,
            "keywords": [product_name.lower()]
        }
        
        logger.info("=" * 80)
        logger.info("FALLBACK SEARCH QUERY PARSER")
        logger.info(f"  Product Name: {product_name}")
        logger.info(f"  Search Request:")
        logger.info(f"    sport: {result['sport']}")
        logger.info(f"    category_level_1: {result['category_level_1']}")
        logger.info(f"    keywords: {result['keywords']}")
        logger.info("=" * 80)
        
        return result
