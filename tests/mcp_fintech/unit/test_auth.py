"""Unit tests for _auth() — auth/permission/audit logic with mocked asyncpg."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import server

pytestmark = pytest.mark.unit


def make_pool(
    consumer_row: dict | None, counter_row: dict | None = None, audit_id: str = "audit-uuid-1"
) -> AsyncMock:
    """Construye un asyncpg.Pool mockeado que responde a fetchrow/fetchval/execute."""
    conn = AsyncMock()

    async def fetchrow(query, *args):
        if "FROM api_consumers" in query:
            return consumer_row
        if "FROM rate_limit_counter" in query:
            return counter_row
        return None

    async def fetchval(query, *args):
        return audit_id

    conn.fetchrow.side_effect = fetchrow
    conn.fetchval.side_effect = fetchval
    conn.execute = AsyncMock(return_value=None)

    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    pool.acquire.return_value.__aexit__.return_value = None
    return pool


@pytest.fixture
def user_row():
    return {
        "id": "consumer-uuid-user",
        "nombre": "María García",
        "rol": "user",
        "permisos": json.dumps(["cuentas:read", "gastos:read"]),
        "rate_limit_hora": 100,
        "activo": True,
    }


@pytest.fixture
def admin_row():
    return {
        "id": "consumer-uuid-admin",
        "nombre": "Admin Fintech",
        "rol": "admin",
        "permisos": json.dumps(
            [
                "cuentas:read",
                "cuentas:write",
                "transferencias:read",
                "transferencias:write",
                "gastos:read",
                "gastos:write",
            ]
        ),
        "rate_limit_hora": 100,
        "activo": True,
    }


async def test_auth_sin_api_key_lanza_401():
    pool = make_pool(consumer_row=None)

    with pytest.raises(PermissionError) as exc:
        await server._auth(pool, api_key="", tool="fintech_ver_saldo", params={})

    assert str(exc.value).startswith("401::")


async def test_auth_api_key_invalida_lanza_401():
    pool = make_pool(consumer_row=None)

    with pytest.raises(PermissionError) as exc:
        await server._auth(pool, api_key="key-xyz", tool="fintech_ver_saldo", params={})

    assert str(exc.value).startswith("401::")


async def test_auth_consumer_desactivado_lanza_403(user_row):
    user_row["activo"] = False
    pool = make_pool(consumer_row=user_row)

    with pytest.raises(PermissionError) as exc:
        await server._auth(pool, "key", "fintech_ver_saldo", {})

    assert str(exc.value).startswith("403::")
    assert "desactivado" in str(exc.value)


async def test_auth_user_lee_cuentas_ok(user_row):
    pool = make_pool(consumer_row=user_row)

    result = await server._auth(pool, "key", "fintech_ver_saldo", {})

    assert result["consumer"]["rol"] == "user"
    assert result["audit_id"] == "audit-uuid-1"


async def test_auth_user_intenta_escritura_lanza_403(user_row):
    pool = make_pool(consumer_row=user_row)

    with pytest.raises(PermissionError) as exc:
        await server._auth(pool, "key", "fintech_crear_cuenta", {})

    msg = str(exc.value)
    assert msg.startswith("403::")
    assert "cuentas:write" in msg
    assert "user" in msg


async def test_auth_admin_puede_todo(admin_row):
    pool = make_pool(consumer_row=admin_row)

    for tool in [
        "fintech_crear_cuenta",
        "fintech_realizar_transferencia",
        "fintech_establecer_presupuesto",
        "fintech_ver_auditoria",
    ]:
        result = await server._auth(pool, "key", tool, {})
        assert result["consumer"]["rol"] == "admin"


async def test_auth_rate_limit_alcanzado_lanza_429(user_row):
    counter = {"total_llamadas": 100}  # rate_limit_hora == 100
    pool = make_pool(consumer_row=user_row, counter_row=counter)

    with pytest.raises(PermissionError) as exc:
        await server._auth(pool, "key", "fintech_ver_saldo", {})

    assert str(exc.value).startswith("429::")
