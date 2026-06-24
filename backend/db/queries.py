"""
Database queries module
Centralized SQL queries for reusability
"""

# Product queries
GET_PRODUCT_BY_ID = """
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

GET_PRODUCTS_BY_IDS = """
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
    WHERE product_id IN %s
    ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST;
"""

SEARCH_PRODUCTS_WITH_FILTERS = """
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
        {sport_filter}
        {category_1_filter}
        {category_2_filter}
        {price_filter}
        {keywords_filter}
    ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST
    LIMIT %s;
"""

SEMANTIC_SEARCH_WITH_FILTER = """
    SELECT 
        p.product_id,
        p.name,
        p.brand,
        p.price,
        p.mrp,
        p.sport,
        p.category_level_1,
        p.category_level_2,
        p.description,
        p.image_url,
        p.product_url,
        p.rating,
        p.review_count,
        1 - (pe.embedding <=> %s::vector) AS similarity
    FROM products p
    JOIN product_embeddings pe ON p.product_id = pe.product_id
    WHERE p.product_id = ANY(%s)
    ORDER BY pe.embedding <=> %s::vector
    LIMIT %s;
"""

GET_CATEGORIES = """
    SELECT DISTINCT
        sport,
        category_level_1,
        category_level_2
    FROM products
    WHERE sport IS NOT NULL
    ORDER BY sport, category_level_1, category_level_2;
"""
