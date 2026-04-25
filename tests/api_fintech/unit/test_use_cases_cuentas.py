"""Unit tests for cuentas use cases — pure logic, no DB."""

import pytest
from application.use_cases.cuentas import (
    CrearCuentaUseCase,
    GetCuentasUseCase,
    GetMovimientosUseCase,
    GetSaldoUseCase,
)
from domain.exceptions import NotFoundError

from .fakes import FakeCuentaRepo, seed_cliente_con_cuenta

pytestmark = pytest.mark.unit


def test_get_cuentas_devuelve_cuentas_del_cliente():
    repo = FakeCuentaRepo()
    seed_cliente_con_cuenta(repo)

    result = GetCuentasUseCase(repo).execute("cliente-001")

    assert result["cliente_id"] == "cliente-001"
    assert result["nombre"] == "Test User"
    assert len(result["cuentas"]) == 1
    assert result["cuentas"][0]["id"] == "CTA-T01"


def test_get_cuentas_cliente_inexistente_lanza_not_found():
    repo = FakeCuentaRepo()

    with pytest.raises(NotFoundError, match="cliente-999"):
        GetCuentasUseCase(repo).execute("cliente-999")


def test_get_saldo_devuelve_saldo_correcto():
    repo = FakeCuentaRepo()
    seed_cliente_con_cuenta(repo)

    result = GetSaldoUseCase(repo).execute("CTA-T01")

    assert result["saldo"] == 1000.0
    assert result["moneda"] == "PEN"
    assert result["tipo"] == "ahorros"


def test_get_saldo_cuenta_inexistente_lanza_not_found():
    repo = FakeCuentaRepo()

    with pytest.raises(NotFoundError):
        GetSaldoUseCase(repo).execute("CTA-NOPE")


def test_get_movimientos_respeta_limite():
    repo = FakeCuentaRepo()
    seed_cliente_con_cuenta(repo)

    result = GetMovimientosUseCase(repo).execute("CTA-T01", limit=1)

    assert result["total"] == 1
    assert len(result["movimientos"]) == 1


def test_get_movimientos_cuenta_inexistente_lanza_not_found():
    repo = FakeCuentaRepo()

    with pytest.raises(NotFoundError):
        GetMovimientosUseCase(repo).execute("CTA-NOPE", limit=10)


def test_crear_cuenta_genera_id_y_asocia_al_cliente():
    repo = FakeCuentaRepo()
    seed_cliente_con_cuenta(repo)

    result = CrearCuentaUseCase(repo).execute("cliente-001", tipo="corriente", moneda="USD")

    assert result["mensaje"] == "Cuenta creada"
    assert result["cuenta"]["tipo"] == "corriente"
    assert result["cuenta"]["moneda"] == "USD"
    assert result["cuenta"]["saldo"] == 0.0
    # cliente debe tener ahora 2 cuentas
    assert len(repo.clientes["cliente-001"].cuentas) == 2


def test_crear_cuenta_cliente_inexistente_lanza_not_found():
    repo = FakeCuentaRepo()

    with pytest.raises(NotFoundError):
        CrearCuentaUseCase(repo).execute("cliente-999", tipo="ahorros", moneda="PEN")
