"""
Database connection module.
Handles PostgreSQL connections with connection pooling.
"""
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import logging
from config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)

logger = logging.getLogger(__name__)

# Connection pool
connection_pool = None


def initialize_pool(minconn=1, maxconn=10):
    """Initialize the connection pool."""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn,
            maxconn,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        logger.info("Database connection pool initialized")
        return connection_pool
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def connect_db():
    """
    Get a database connection from the pool.
    Returns a connection object with RealDictCursor for dict-like results.
    """
    global connection_pool
    
    if connection_pool is None:
        initialize_pool()
    
    try:
        conn = connection_pool.getconn()
        logger.debug("Database connection acquired from pool")
        return conn
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise


def release_connection(conn):
    """Return a connection to the pool."""
    global connection_pool
    if connection_pool and conn:
        connection_pool.putconn(conn)
        logger.debug("Database connection returned to pool")


def close_pool():
    """Close all connections in the pool."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        logger.info("Database connection pool closed")


def execute_query(query, params=None, fetch=True):
    """
    Execute a query and return results.
    
    Args:
        query: SQL query string
        params: Query parameters (tuple)
        fetch: Whether to fetch results (default True)
    
    Returns:
        List of dictionaries for SELECT queries, or None for INSERT/UPDATE/DELETE
    """
    conn = None
    try:
        conn = connect_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            if fetch:
                results = cursor.fetchall()
                return [dict(row) for row in results]
            else:
                conn.commit()
                return None
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Query execution failed: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)
