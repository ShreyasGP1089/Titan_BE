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
        
        Simply retrieves products by IDs.
        The Workflow Agent will do the actual comparison.
        
        Args:
            arguments: CompareArguments with product IDs
        
        Returns:
            CompareResponse with products
        """
        product_ids = arguments.products
        
        logger.info(f"Executing compare: products={product_ids}")
        
        if len(product_ids) < 2:
            raise ValueError("At least 2 products required for comparison")
        
        # Retrieve products
        products = self._get_products_by_ids(product_ids)
        
        # Convert to Product objects
        product_objects = [Product(**p) for p in products]
        
        response = CompareResponse(
            products=product_objects
        )
        
        logger.info(f"Compare returned {len(product_objects)} products")
        
        return response
    
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
