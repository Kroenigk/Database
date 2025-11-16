import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

_pool = None

def _init_pool():
    global _pool
    if _pool is None:
        config = {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "database": os.getenv("DB_NAME", "parksdb"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", "rootpass"),
        }
        _pool = pooling.MySQLConnectionPool(pool_name="parks_pool",
                                            pool_size=5,
                                            pool_reset_session=True,
                                            **config)

def get_connection():
    """Return a pooled MySQL connection."""
    if _pool is None:
        _init_pool()
    return _pool.get_connection()

@contextmanager
def cursor(commit: bool = False):
    """
    Context manager yielding a cursor and handling commit/rollback.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        cur.close()
        conn.close()

def fetch_all(sql: str, params=None):
    """Execute a SELECT and return all rows."""
    with cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()

def fetch_one(sql: str, params=None):
    """Execute a SELECT and return first row or None."""
    with cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchone()

def execute(sql: str, params=None):
    """Execute mutation SQL."""
    with cursor(commit=True) as cur:
        cur.execute(sql, params or [])

def executemany(sql: str, seq_params):
    """Bulk execute many rows."""
    with cursor(commit=True) as cur:
        cur.executemany(sql, seq_params)

# TODO: Add logging wrappers / retry logic.
