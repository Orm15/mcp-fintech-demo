"""Unit tests for the static TOOL_PERMISSIONS map — guards the contract."""

import pytest
import server  # mcp-fintech/server.py — added to sys.path in tests/conftest.py

pytestmark = pytest.mark.unit


def test_all_tools_have_permissions():
    """Cada tool MCP debe tener un permiso requerido declarado.

    13 tools de negocio + 3 variantes HTML (server-rendered para comparación visual) = 16.
    """
    assert len(server.TOOL_PERMISSIONS) == 16
    # Cada variante HTML hereda el permiso de su contraparte JSON.
    pairs = [
        ("fintech_resumen_gastos_html", "fintech_resumen_gastos"),
        ("fintech_consultar_cuentas_html", "fintech_consultar_cuentas"),
        ("fintech_ver_auditoria_html", "fintech_ver_auditoria"),
    ]
    for html_tool, json_tool in pairs:
        assert (
            server.TOOL_PERMISSIONS[html_tool] == server.TOOL_PERMISSIONS[json_tool]
        ), f"{html_tool} debería tener mismo permiso que {json_tool}"


def test_admin_only_tools_require_write_permission():
    """Tools de escritura/auditoría requieren permisos *:write."""
    admin_only = [
        "fintech_crear_cuenta",
        "fintech_realizar_transferencia",
        "fintech_establecer_presupuesto",
        "fintech_ver_auditoria",
    ]
    for tool in admin_only:
        perm = server.TOOL_PERMISSIONS[tool]
        assert perm.endswith(":write"), f"{tool} debería requerir :write, tiene {perm}"


def test_read_tools_use_read_permissions():
    read_tools = {
        "fintech_consultar_cuentas": "cuentas:read",
        "fintech_ver_saldo": "cuentas:read",
        "fintech_ver_movimientos": "cuentas:read",
        "fintech_estado_transferencia": "transferencias:read",
        "fintech_historial_transferencias": "transferencias:read",
        "fintech_consultar_limites": "transferencias:read",
        "fintech_resumen_gastos": "gastos:read",
        "fintech_detalle_categorias": "gastos:read",
        "fintech_ver_alertas": "gastos:read",
    }
    for tool, expected in read_tools.items():
        assert server.TOOL_PERMISSIONS[tool] == expected


def test_auditoria_es_exclusiva_de_admin():
    """fintech_ver_auditoria debe requerir cuentas:write — solo el admin la tiene."""
    assert server.TOOL_PERMISSIONS["fintech_ver_auditoria"] == "cuentas:write"
