import os
import yaml
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from dotenv import load_dotenv
from utils.logger import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

with open(os.path.join(BASE_DIR, "config.yaml"), "r") as f:
    _cfg = yaml.safe_load(f)

_db_cfg = _cfg["database"]
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

_pool = None


def get_pool() -> pool.ThreadedConnectionPool:
    """Get or create the connection pool singleton."""
    global _pool
    if _pool is None or _pool.closed:
        log.info("Creating database connection pool")
        _pool = pool.ThreadedConnectionPool(
            minconn=_db_cfg.get("pool_min", 2),
            maxconn=_db_cfg.get("pool_max", 10),
            host=_db_cfg["host"],
            port=_db_cfg["port"],
            dbname=_db_cfg["name"],
            user=_db_cfg["user"],
            password=DB_PASSWORD,
        )
    return _pool


class DBContext:
    """
    Context manager for database operations.
    Yields (cursor, connection). Auto-commits on success, rolls back on error.
    
    Usage:
        with DBContext() as (cur, conn):
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    """

    def __init__(self):
        self._conn = None
        self._cur = None

    def __enter__(self):
        p = get_pool()
        self._conn = p.getconn()
        self._cur = self._conn.cursor()
        return self._cur, self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
                log.error(f"DB transaction rolled back: {exc_val}")
        finally:
            if self._cur and not self._cur.closed:
                self._cur.close()
            if self._conn:
                try:
                    get_pool().putconn(self._conn)
                except Exception:
                    pass
        return False  # Do not suppress exceptions
