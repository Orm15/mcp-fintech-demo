"""
Integration test fixtures: spin up a real Postgres via testcontainers,
load the schema + minimal seed, expose a connected pool to tests.

Requires: docker (orbstack/colima/desktop) and Python 3.12 (psycopg2-binary
has no 3.13 wheels yet — these tests run in CI on 3.12).
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import psycopg2  # noqa: F401
    from testcontainers.postgres import PostgresContainer

    HAS_PG = True
except ImportError:
    HAS_PG = False


pytestmark = pytest.mark.skipif(
    not HAS_PG,
    reason="psycopg2 / testcontainers not installed (Python 3.13 lacks psycopg2 wheels)",
)


ROOT = Path(__file__).resolve().parents[3]
INIT_SQL = ROOT / "postgres" / "init.sql"


@pytest.fixture(scope="session")
def pg_container():
    """Postgres ephemeral container — schema + seeds loaded once per session."""
    if not HAS_PG:
        pytest.skip("psycopg2 not installed")

    with PostgresContainer(
        "postgres:16-alpine", username="fintech", password="fintech123", dbname="fintechdb"
    ) as pg:
        # Load init.sql
        import psycopg2

        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(INIT_SQL.read_text())
            conn.commit()
        yield pg


@pytest.fixture(scope="session")
def pg_dsn(pg_container):
    return pg_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture
def pg_pool(pg_dsn, monkeypatch):
    """Inicializa el pool global de api-fintech apuntando al testcontainer."""
    monkeypatch.setenv("DATABASE_URL", pg_dsn)
    from infrastructure import database

    database._pool = None  # reset module-level singleton
    database.init_pool(retries=2, delay=0.5)
    yield database._pool
    database._pool.closeall()
    database._pool = None
