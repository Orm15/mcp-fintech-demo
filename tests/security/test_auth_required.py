"""401: tools no se pueden llamar sin API key válida."""

import pytest

pytestmark = pytest.mark.security


def test_sin_api_key_devuelve_401(mcp_session):
    result = mcp_session("fintech_ver_saldo", {"cuenta_id": "CTA-001"}, api_key=None)

    assert result.get("status") == 401
    assert "key" in result.get("error", "").lower()


def test_api_key_invalida_devuelve_401(mcp_session):
    result = mcp_session("fintech_ver_saldo", {"cuenta_id": "CTA-001"}, api_key="key-no-existe-xyz")

    assert result.get("status") == 401


def test_api_key_vacia_devuelve_401(mcp_session):
    result = mcp_session("fintech_ver_saldo", {"cuenta_id": "CTA-001"}, api_key="")

    assert result.get("status") == 401
