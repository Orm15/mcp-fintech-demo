"""403: usuario sin permiso debe ser bloqueado por cada tool restringido."""

import pytest

from .conftest import ADMIN_KEY, USER_KEY

pytestmark = pytest.mark.security

# Tools que requieren permisos write — el rol "user" NO debe poder ejecutarlos.
WRITE_TOOLS = [
    ("fintech_crear_cuenta", {"cliente_id": "cliente-001", "tipo": "ahorros"}),
    ("fintech_realizar_transferencia", {"origen": "CTA-001", "destino": "CTA-003", "monto": 1.0}),
    ("fintech_establecer_presupuesto", {"cliente_id": "cliente-001", "categoria": "Salud", "monto": 100.0}),
    ("fintech_ver_auditoria", {"limite": 5}),
]


@pytest.mark.parametrize("tool,args", WRITE_TOOLS)
def test_user_no_puede_ejecutar_writes(mcp_session, tool, args):
    result = mcp_session(tool, args, api_key=USER_KEY)

    assert result.get("status") == 403
    assert "permiso" in result.get("error", "").lower()


def test_admin_puede_ver_auditoria(mcp_session):
    result = mcp_session("fintech_ver_auditoria", {"limite": 3}, api_key=ADMIN_KEY)

    assert "registros" in result
    assert isinstance(result["registros"], list)


def test_user_puede_leer_su_propia_data(mcp_session):
    result = mcp_session("fintech_ver_saldo", {"cuenta_id": "CTA-001"}, api_key=USER_KEY)

    assert "saldo" in result
