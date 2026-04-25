"""Integration tests: FastAPI HTTP endpoints against the real DB container."""

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def client(pg_pool):
    """TestClient apuntando al api-fintech app con auth deshabilitada (función-key)."""
    os.environ["FUNCTION_KEY"] = "test-key"
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app, headers={"X-Functions-Key": "test-key"})


def test_health(client):
    r = client.get("/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_cuentas_cliente_existente(client):
    r = client.get("/api/cuentas/cliente-001")

    assert r.status_code == 200
    body = r.json()
    assert body["cliente_id"] == "cliente-001"
    assert len(body["cuentas"]) >= 1


def test_get_cuentas_cliente_inexistente_404(client):
    r = client.get("/api/cuentas/cliente-no-existe")

    assert r.status_code == 404


def test_get_saldo_404_si_cuenta_no_existe(client):
    r = client.get("/api/cuentas/CTA-NOPE/saldo")

    assert r.status_code == 404


def test_sin_function_key_devuelve_401(pg_pool):
    """Llamada sin X-Functions-Key debe ser rechazada por la auth global."""
    os.environ["FUNCTION_KEY"] = "test-key"
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)  # SIN header
    r = client.get("/api/cuentas/cliente-001")

    assert r.status_code == 401


def test_function_key_invalida_devuelve_401(pg_pool):
    os.environ["FUNCTION_KEY"] = "test-key"
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, headers={"X-Functions-Key": "wrong"})
    r = client.get("/api/cuentas/cliente-001")

    assert r.status_code == 401


def test_crear_cuenta_201(client):
    r = client.post(
        "/api/cuentas",
        json={
            "cliente_id": "cliente-002",
            "tipo": "ahorros",
            "moneda": "PEN",
        },
    )

    assert r.status_code in (200, 201)
    body = r.json()
    assert body["cuenta"]["cliente_id"] == "cliente-002"


def test_crear_transferencia_y_consultarla(client):
    r = client.post(
        "/api/transferencias",
        json={
            "origen": "CTA-001",
            "destino": "CTA-003",
            "monto": 50.0,
            "descripcion": "test http",
        },
    )

    assert r.status_code in (200, 201)
    trf_id = r.json()["transferencia"]["id"]

    r2 = client.get(f"/api/transferencias/{trf_id}")
    assert r2.status_code == 200
    assert r2.json()["estado"] == "COMPLETADA"


def test_resumen_gastos_devuelve_total(client):
    r = client.get("/api/gastos/cliente-001/resumen")

    assert r.status_code == 200
    body = r.json()
    assert "total_gastado" in body
    assert "por_categoria" in body
