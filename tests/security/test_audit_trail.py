"""Audit trail: toda llamada (exitosa o bloqueada) debe quedar registrada."""

import pytest

from .conftest import ADMIN_KEY, USER_KEY

pytestmark = pytest.mark.security


def test_llamada_403_queda_en_auditoria(mcp_session):
    """Cuando user intenta crear cuenta, el 403 queda en audit_log."""
    # Trigger: user → crear_cuenta (debe fallar 403)
    mcp_session("fintech_crear_cuenta", {"cliente_id": "cliente-001", "tipo": "ahorros"}, api_key=USER_KEY)

    # Verificar via admin → ver_auditoria
    audit = mcp_session("fintech_ver_auditoria", {"limite": 20}, api_key=ADMIN_KEY)

    registros = audit["registros"]
    bloqueos_user = [
        r
        for r in registros
        if r["nombre"] == "María García"
        and r["tool_nombre"] == "fintech_crear_cuenta"
        and r["status_code"] == 403
    ]
    assert len(bloqueos_user) >= 1, f"esperaba al menos un 403 de user/crear_cuenta, vi: {registros}"


def test_llamada_exitosa_registra_latencia(mcp_session):
    """Una lectura ok debe quedar con status 200 y latencia_ms > 0."""
    mcp_session("fintech_ver_saldo", {"cuenta_id": "CTA-001"}, api_key=USER_KEY)

    audit = mcp_session("fintech_ver_auditoria", {"limite": 5}, api_key=ADMIN_KEY)
    registros = audit["registros"]

    lecturas_ok = [
        r
        for r in registros
        if r["tool_nombre"] == "fintech_ver_saldo" and r["status_code"] == 200 and (r["latencia_ms"] or 0) > 0
    ]
    assert len(lecturas_ok) >= 1
