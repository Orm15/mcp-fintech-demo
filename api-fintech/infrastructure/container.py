from adapters.secondary.postgres.cuenta_repo import PostgresCuentaRepository
from adapters.secondary.postgres.gasto_repo import PostgresGastoRepository
from adapters.secondary.postgres.transferencia_repo import PostgresTransferenciaRepository
from application.use_cases.cuentas import (
    CrearCuentaUseCase,
    GetCuentasUseCase,
    GetMovimientosUseCase,
    GetSaldoUseCase,
)
from application.use_cases.gastos import (
    GetAlertasUseCase,
    GetCategoriasUseCase,
    GetResumenUseCase,
    SetPresupuestoUseCase,
)
from application.use_cases.transferencias import (
    CrearTransferenciaUseCase,
    GetHistorialUseCase,
    GetLimitesUseCase,
    GetTransferenciaUseCase,
)

# Repositorios Postgres — un objeto por proceso, conexiones gestionadas por el pool
_cuenta_repo = PostgresCuentaRepository()
_transferencia_repo = PostgresTransferenciaRepository()
_gasto_repo = PostgresGastoRepository()


# ── Cuentas ──────────────────────────────────────────────────────────────────
def get_cuentas_uc() -> GetCuentasUseCase:
    return GetCuentasUseCase(_cuenta_repo)


def get_saldo_uc() -> GetSaldoUseCase:
    return GetSaldoUseCase(_cuenta_repo)


def get_movimientos_uc() -> GetMovimientosUseCase:
    return GetMovimientosUseCase(_cuenta_repo)


def get_crear_cuenta_uc() -> CrearCuentaUseCase:
    return CrearCuentaUseCase(_cuenta_repo)


# ── Transferencias ───────────────────────────────────────────────────────────
def get_crear_transferencia_uc() -> CrearTransferenciaUseCase:
    return CrearTransferenciaUseCase(_transferencia_repo)


def get_transferencia_uc() -> GetTransferenciaUseCase:
    return GetTransferenciaUseCase(_transferencia_repo)


def get_historial_uc() -> GetHistorialUseCase:
    return GetHistorialUseCase(_transferencia_repo)


def get_limites_uc() -> GetLimitesUseCase:
    return GetLimitesUseCase(_transferencia_repo)


# ── Gastos ────────────────────────────────────────────────────────────────────
def get_resumen_uc() -> GetResumenUseCase:
    return GetResumenUseCase(_gasto_repo)


def get_categorias_uc() -> GetCategoriasUseCase:
    return GetCategoriasUseCase(_gasto_repo)


def get_set_presupuesto_uc() -> SetPresupuestoUseCase:
    return SetPresupuestoUseCase(_gasto_repo)


def get_alertas_uc() -> GetAlertasUseCase:
    return GetAlertasUseCase(_gasto_repo)
