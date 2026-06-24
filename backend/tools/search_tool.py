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
            SearchResponse with products
        """
        logger.info(f"Executing search: sport={request.sport}, cat1={request.category_level_1}")
        
        # Perform hybrid search
        products = self.search_service.search(
            sport=request.sport,
            category_level_1=request.category_level_1,
            category_level_2=request.category_level_2,
            keywords=request.keywords,
            price_limit=request.price_limit,
            top_k=10
        )
        
        # Convert to Product schema
        normalized_products = []

        for p in products:
            p = dict(p)

            if p.get("sport") is None:
                p["sport"] = ""

            if p.get("category_level_1") is None:
                p["category_level_1"] = ""

            if p.get("category_level_2") is None:
                p["category_level_2"] = ""

            normalized_products.append(p)

        product_objects = [Product(**p) for p in normalized_products]
        
        response = SearchResponse(
            products=product_objects,
            total=len(product_objects),
            query=request
        )
        
        logger.info(f"Search returned {len(product_objects)} products")
        
        return response
