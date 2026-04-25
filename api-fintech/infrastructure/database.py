import logging
import os
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger("api-fintech")

_pool: ThreadedConnectionPool | None = None


def init_pool(retries: int = 5, delay: float = 3.0) -> None:
    global _pool
    dsn = os.getenv("DATABASE_URL", "postgresql://fintech:fintech123@postgres:5432/fintechdb")
    for attempt in range(1, retries + 1):
        try:
            _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)
            logger.info(f"Pool PostgreSQL creado (intento {attempt})")
            return
        except psycopg2.OperationalError as e:
            logger.warning(f"PostgreSQL no disponible, intento {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(delay)
    raise RuntimeError("No se pudo conectar a PostgreSQL tras varios intentos")


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Pool no inicializado — llama a init_pool() en el lifespan")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
