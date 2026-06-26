"""
Search Tool
Executes search intent requests
"""
import logging
from typing import List, Dict
from models.schemas import SearchRequest, SearchResponse, Product
from services.hybrid_search import HybridSearchService

logger = logging.getLogger(__name__)


class SearchTool:
    """Tool for executing search intent"""
    
    def __init__(self):
        self.search_service = HybridSearchService()
    
    def execute(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search request.
        
        Args:
            request: SearchRequest with sport, categories, keywords, price_limit
        
        Returns:
            SearchResponse with products (RELEVANT) and related (RELATED)
        """
        logger.info(f"Executing search: sport={request.sport}, cat1={request.category_level_1}")
        
        # Perform hybrid search
        result = self.search_service.search(
            sport=request.sport,
            category_level_1=request.category_level_1,
            category_level_2=request.category_level_2,
            keywords=request.keywords,
            price_limit=request.price_limit,
            top_k=10,
            return_format='dict'  # External API: return separate relevant/related lists
        )
        
        # Handle new dict format with separate relevant/related lists
        if isinstance(result, dict):
            relevant_products = result.get('relevant', [])
            related_products = result.get('related', [])
        else:
            # Fallback for old format
            relevant_products = result
            related_products = []
        
        # Normalize products
        def normalize_product_list(products):
            normalized = []
            for p in products:
                p_dict = dict(p)
                if p_dict.get("sport") is None:
                    p_dict["sport"] = ""
                if p_dict.get("category_level_1") is None:
                    p_dict["category_level_1"] = ""
                if p_dict.get("category_level_2") is None:
                    p_dict["category_level_2"] = ""
                normalized.append(p_dict)
            return normalized
        
        relevant_normalized = normalize_product_list(relevant_products)
        related_normalized = normalize_product_list(related_products)
        
        # Convert to Product objects
        relevant_objects = [Product(**p) for p in relevant_normalized]
        related_objects = [Product(**p) for p in related_normalized]
        
        response = SearchResponse(
            products=relevant_objects,
            related=related_objects,
            total=len(relevant_objects),
            related_total=len(related_objects),
            query=request
        )
        
        logger.info(f"Search returned {len(relevant_objects)} RELEVANT products, {len(related_objects)} RELATED products")
        
        return response
