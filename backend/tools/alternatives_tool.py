"""
Alternatives Tool
Finds alternative products similar to a given product
"""
import logging
from typing import List, Dict
from psycopg2.extras import RealDictCursor
from models.schemas import AlternativesArguments, AlternativesResponse, Product
from database import connect_db, release_connection
from services.hybrid_search import convert_decimals

logger = logging.getLogger(__name__)


class AlternativesTool:
    """Tool for finding product alternatives"""
    
    def execute(self, arguments: AlternativesArguments) -> AlternativesResponse:
        """
        Execute alternatives request.
        
        Flow:
            1. Find source product
            2. Extract: sport, category_level_1, price
            3. Search: same sport, same category, price within ±30%
            4. Exclude original product
            5. Return alternatives
        
        Args:
            arguments: AlternativesArguments with product ID
        
        Returns:
            AlternativesResponse with alternative products
        """
        product_id = arguments.product
        
        logger.info(f"Executing alternatives: product={product_id}")
        
        # Get source product
        source_product = self._get_product_by_id(product_id)
        
        if not source_product:
            logger.error(f"Product not found: {product_id}")
            raise ValueError(f"Product '{product_id}' not found")
        
        # Extract attributes
        sport = source_product['sport']
        category_level_1 = source_product['category_level_1']
        price = float(source_product['price'])
        
        # Calculate price range (±30%)
        price_min = price * 0.7
        price_max = price * 1.3
        
        logger.info(f"Source: {source_product['name']}")
        logger.info(f"Sport: {sport}, Category: {category_level_1}")
        logger.info(f"Price range: ₹{price_min:.2f} - ₹{price_max:.2f}")
        
        # Search for alternatives
        alternatives = self._search_alternatives(
            sport=sport,
            category_level_1=category_level_1,
            price_min=price_min,
            price_max=price_max,
            exclude_product_id=product_id
        )
        
        # Convert to Product objects
        product_objects = [Product(**p) for p in alternatives]
        
        response = AlternativesResponse(
            source_product=Product(**source_product),
            products=product_objects,
            total=len(product_objects)
        )
        
        logger.info(f"Found {len(product_objects)} alternatives")
        
        return response
    
    def _get_product_by_id(self, product_id: str) -> Dict:
        """
        Get product by ID.
        
        Args:
            product_id: Product ID
        
        Returns:
            Product dictionary or None
        """
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
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
                WHERE product_id = %s;
            """
            
            cur.execute(query, (product_id,))
            result = cur.fetchone()
            
            if result:
                return convert_decimals(dict(result))
            return None
            
        except Exception as e:
            logger.error(f"Error fetching product: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)
    
    def _search_alternatives(
        self,
        sport: str,
        category_level_1: str,
        price_min: float,
        price_max: float,
        exclude_product_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search for alternative products.
        
        Criteria:
            - Same sport
            - Same category_level_1
            - Price within range
            - Exclude original product
        
        Args:
            sport: Sport category
            category_level_1: Category level 1
            price_min: Minimum price
            price_max: Maximum price
            exclude_product_id: Product ID to exclude
            limit: Maximum results
        
        Returns:
            List of product dictionaries
        """
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
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
                WHERE 
                    LOWER(sport) = LOWER(%s)
                    AND LOWER(category_level_1) = LOWER(%s)
                    AND price BETWEEN %s AND %s
                    AND product_id != %s
                ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST
                LIMIT %s;
            """
            
            cur.execute(query, (sport, category_level_1, price_min, price_max, exclude_product_id, limit))
            results = cur.fetchall()
            
            logger.info(f"Found {len(results)} alternatives")
            
            return [convert_decimals(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Error searching alternatives: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)
