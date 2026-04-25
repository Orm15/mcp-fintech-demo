"""
Input validation: payloads maliciosos no deben crashear el server ni
exponer datos. Los errores deben ser controlados (no 500/stack traces).
"""

import pytest

from .conftest import USER_KEY

pytestmark = pytest.mark.security


def test_sql_injection_en_cuenta_id(mcp_session):
    """Un id con SQL injection NO debe ejecutar SQL — query parametrizada."""
    payload = "CTA-001'; DROP TABLE cuentas; --"

    result = mcp_session("fintech_ver_saldo", {"cuenta_id": payload}, api_key=USER_KEY)

    error_msg = (result.get("error", "") + str(result.get("raw", ""))).lower()

    # Señal de éxito: NO se ejecutó SQL (la query parametrizada en el repo lo evitó).
    # Lo verificamos por ausencia de errores típicos de SQL y porque la tabla sigue existiendo.
    assert "syntax error" not in error_msg
    assert "psycopg" not in error_msg
    assert "asyncpg" not in error_msg

    # Verificación crítica: la tabla cuentas SIGUE existiendo (lectura posterior debe funcionar)
    sanity = mcp_session("fintech_ver_saldo", {"cuenta_id": "CTA-001"}, api_key=USER_KEY)
    assert "saldo" in sanity, "cuentas table parece haber sido afectada — INYECCIÓN EXITOSA"


def test_payload_oversized_no_crashea(mcp_session):
    """Un descripcion muy larga no debe crashear el server."""
    big = "A" * 10_000

    # No usamos admin para evitar persistir basura — nos basta con que NO crashee
    result = mcp_session(
        "fintech_realizar_transferencia",
        {"origen": "CTA-001", "destino": "CTA-003", "monto": 1.0, "descripcion": big},
        api_key=USER_KEY,
    )

    # user no tiene permiso → 403 controlado (no 500)
    assert result.get("status") in (403, 400, 422)


def test_monto_negativo_es_rechazado_por_pydantic(mcp_session):
    """Pydantic Field(gt=0) debe rechazar montos negativos antes de llegar a la BD."""
    result = mcp_session(
        "fintech_realizar_transferencia",
        {"origen": "CTA-001", "destino": "CTA-003", "monto": -100.0},
        api_key=USER_KEY,
    )

    raw = result.get("raw", "") or result.get("error", "")
    # FastMCP devuelve el error de validación como text
    assert (
        "Input should be greater than 0" in raw
        or "validation" in raw.lower()
        or result.get("status") in (400, 422, 403)
    )


def test_tipos_incorrectos_son_rechazados(mcp_session):
    """Pasar string donde se espera int debe fallar la validación."""
    result = mcp_session(
        "fintech_ver_movimientos", {"cuenta_id": "CTA-001", "limit": "no-soy-un-int"}, api_key=USER_KEY
    )

    raw = result.get("raw", "") or str(result)
    assert "validation" in raw.lower() or "Input" in raw or result.get("status") in (400, 422)
