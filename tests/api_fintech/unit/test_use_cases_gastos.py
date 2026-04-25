"""Unit tests for gastos use cases."""

import pytest
from application.use_cases.gastos import (
    GetAlertasUseCase,
    GetCategoriasUseCase,
    GetResumenUseCase,
    SetPresupuestoUseCase,
)
from domain.exceptions import NotFoundError

from .fakes import FakeGastoRepo, seed_gastos

pytestmark = pytest.mark.unit


def test_resumen_calcula_total_correctamente():
    repo = FakeGastoRepo()
    seed_gastos(repo)

    result = GetResumenUseCase(repo).execute("cliente-001")

    # 400 (Alimentación) + 180 (Transporte) = 580
    assert result["total_gastado"] == 580.0
    assert result["mes"] == "2026-04"
    assert "Alimentación" in result["por_categoria"]


def test_resumen_cliente_inexistente_lanza_not_found():
    repo = FakeGastoRepo()

    with pytest.raises(NotFoundError):
        GetResumenUseCase(repo).execute("cliente-999")


def test_categorias_marca_excedido_cuando_supera_presupuesto():
    repo = FakeGastoRepo()
    seed_gastos(repo)

    result = GetCategoriasUseCase(repo).execute("cliente-001")

    # Alimentación: gastado 400 > presupuesto 350 → excedido
    assert result["categorias"]["Alimentación"]["excedido"] is True
    # Transporte: gastado 180 < presupuesto 200 → no excedido
    assert result["categorias"]["Transporte"]["excedido"] is False


def test_set_presupuesto_persiste_y_devuelve_monto():
    repo = FakeGastoRepo()

    result = SetPresupuestoUseCase(repo).execute("cliente-001", "Salud", 500.0)

    assert result["mensaje"] == "Presupuesto actualizado"
    assert repo.presupuestos["cliente-001"]["Salud"] == 500.0


def test_alertas_solo_categorias_excedidas():
    repo = FakeGastoRepo()
    seed_gastos(repo)

    result = GetAlertasUseCase(repo).execute("cliente-001")

    assert result["total_alertas"] == 1
    alerta = result["alertas"][0]
    assert alerta["categoria"] == "Alimentación"
    assert alerta["exceso"] == 50.0  # 400 - 350
    assert alerta["pct_excedido"] > 14  # ~14.3%


def test_alertas_sin_excesos_devuelve_lista_vacia():
    repo = FakeGastoRepo()
    seed_gastos(repo)
    # subir el presupuesto para que ya no haya exceso
    repo.presupuestos["cliente-001"]["Alimentación"] = 1000.0

    result = GetAlertasUseCase(repo).execute("cliente-001")

    assert result["total_alertas"] == 0
