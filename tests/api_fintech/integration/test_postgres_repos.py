"""Integration tests: postgres adapters against a real container."""

import pytest

pytestmark = pytest.mark.integration


def test_cuenta_repo_lee_seed(pg_pool):
    from adapters.secondary.postgres.cuenta_repo import PostgresCuentaRepository

    repo = PostgresCuentaRepository()
    cliente = repo.get_cliente("cliente-001")

    assert cliente is not None
    assert cliente.nombre  # tiene nombre
    assert len(cliente.cuentas) >= 1


def test_cuenta_repo_get_cuenta_devuelve_saldo(pg_pool):
    from adapters.secondary.postgres.cuenta_repo import PostgresCuentaRepository

    repo = PostgresCuentaRepository()
    cuenta = repo.get_cuenta("CTA-001")

    assert cuenta is not None
    assert cuenta.saldo > 0
    assert cuenta.estado == "activa"


def test_cuenta_repo_crear_cuenta_persiste(pg_pool):
    from adapters.secondary.postgres.cuenta_repo import PostgresCuentaRepository

    repo = PostgresCuentaRepository()
    nueva = repo.crear_cuenta("cliente-001", "ahorros", "PEN")

    assert nueva.id.startswith("CTA-")
    # leerla de nuevo desde la BD
    leida = repo.get_cuenta(nueva.id)
    assert leida is not None
    assert leida.saldo == 0.0


def test_cuenta_repo_movimientos_ordenados_desc(pg_pool):
    from adapters.secondary.postgres.cuenta_repo import PostgresCuentaRepository

    repo = PostgresCuentaRepository()
    movs = repo.get_movimientos("CTA-001", limit=10)

    assert len(movs) > 0
    # fechas descendentes
    fechas = [m.fecha for m in movs]
    assert fechas == sorted(fechas, reverse=True)


def test_transferencia_repo_get_existente(pg_pool):
    from adapters.secondary.postgres.transferencia_repo import PostgresTransferenciaRepository

    repo = PostgresTransferenciaRepository()
    trf = repo.get_by_id("TRF-001")

    assert trf is not None
    assert trf.estado in ("COMPLETADA", "PENDIENTE", "FALLIDA")


def test_transferencia_repo_crear_actualiza_saldos(pg_pool):
    from adapters.secondary.postgres.cuenta_repo import PostgresCuentaRepository
    from adapters.secondary.postgres.transferencia_repo import PostgresTransferenciaRepository

    cr = PostgresCuentaRepository()
    tr = PostgresTransferenciaRepository()

    saldo_origen_antes = cr.get_cuenta("CTA-001").saldo
    saldo_destino_antes = cr.get_cuenta("CTA-003").saldo

    trf = tr.crear("CTA-001", "CTA-003", 100.0, "test integration")

    assert trf.estado == "COMPLETADA"
    assert cr.get_cuenta("CTA-001").saldo == saldo_origen_antes - 100.0
    assert cr.get_cuenta("CTA-003").saldo == saldo_destino_antes + 100.0


def test_gasto_repo_resumen_seed(pg_pool):
    from adapters.secondary.postgres.gasto_repo import PostgresGastoRepository

    repo = PostgresGastoRepository()
    datos = repo.get_datos("cliente-001")

    assert datos is not None
    assert len(datos.categorias) > 0


def test_gasto_repo_set_presupuesto_upsert(pg_pool):
    from adapters.secondary.postgres.gasto_repo import PostgresGastoRepository

    repo = PostgresGastoRepository()
    repo.set_presupuesto("cliente-001", "Salud", 999.0)
    repo.set_presupuesto("cliente-001", "Salud", 555.0)  # debe actualizar

    presups = repo.get_presupuestos("cliente-001")
    assert presups["Salud"] == 555.0
