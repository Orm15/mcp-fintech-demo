"""Unit tests for transferencias use cases."""

import pytest
from application.use_cases.transferencias import (
    CrearTransferenciaUseCase,
    GetHistorialUseCase,
    GetLimitesUseCase,
    GetTransferenciaUseCase,
)
from domain.entities.transferencia import LimiteTransferencia
from domain.exceptions import NotFoundError

from .fakes import FakeTransferenciaRepo

pytestmark = pytest.mark.unit


def test_crear_transferencia_devuelve_estado_completada():
    repo = FakeTransferenciaRepo()

    result = CrearTransferenciaUseCase(repo).execute(
        origen="CTA-001",
        destino="CTA-002",
        monto=100.0,
        descripcion="test",
    )

    assert result["mensaje"] == "Transferencia ejecutada"
    assert result["transferencia"]["estado"] == "COMPLETADA"
    assert result["transferencia"]["monto"] == 100.0


def test_get_transferencia_existente():
    repo = FakeTransferenciaRepo()
    CrearTransferenciaUseCase(repo).execute("CTA-001", "CTA-002", 50.0, "x")
    trf_id = next(iter(repo.transferencias.keys()))

    result = GetTransferenciaUseCase(repo).execute(trf_id)

    assert result["id"] == trf_id
    assert result["estado"] == "COMPLETADA"


def test_get_transferencia_inexistente_lanza_not_found():
    repo = FakeTransferenciaRepo()

    with pytest.raises(NotFoundError):
        GetTransferenciaUseCase(repo).execute("TRF-NOPE")


def test_historial_incluye_enviadas_y_recibidas():
    repo = FakeTransferenciaRepo()
    CrearTransferenciaUseCase(repo).execute("CTA-001", "CTA-002", 50.0, "out")
    CrearTransferenciaUseCase(repo).execute("CTA-003", "CTA-001", 30.0, "in")

    result = GetHistorialUseCase(repo).execute("CTA-001")

    assert result["total"] == 2


def test_historial_cuenta_sin_movimientos_devuelve_lista_vacia():
    repo = FakeTransferenciaRepo()

    result = GetHistorialUseCase(repo).execute("CTA-VACIA")

    assert result["total"] == 0
    assert result["transferencias"] == []


def test_get_limites_devuelve_disponible():
    repo = FakeTransferenciaRepo()
    repo.limites["cliente-001"] = LimiteTransferencia(
        limite_diario=5000.0,
        usado_hoy=1500.0,
        moneda="PEN",
        disponible_hoy=3500.0,
        cliente_id="cliente-001",
    )

    result = GetLimitesUseCase(repo).execute("cliente-001")

    assert result["disponible_hoy"] == 3500.0
    assert result["limite_diario"] == 5000.0


def test_get_limites_cliente_inexistente_lanza_not_found():
    repo = FakeTransferenciaRepo()

    with pytest.raises(NotFoundError):
        GetLimitesUseCase(repo).execute("cliente-999")
