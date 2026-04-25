from application.use_cases.cuentas import (
    CrearCuentaUseCase,
    GetCuentasUseCase,
    GetMovimientosUseCase,
    GetSaldoUseCase,
)
from domain.exceptions import NotFoundError
from fastapi import APIRouter, Depends, Header, HTTPException
from infrastructure.container import (
    get_crear_cuenta_uc,
    get_cuentas_uc,
    get_movimientos_uc,
    get_saldo_uc,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/cuentas", tags=["cuentas"])


class CrearCuentaRequest(BaseModel):
    cliente_id: str
    tipo: str = "ahorros"
    moneda: str = "PEN"


def _log(msg: str, caller: str) -> None:
    print(f"[cuentas] {msg} | caller={caller}", flush=True)


@router.get("/{cuenta_id}/saldo")
def get_saldo(
    cuenta_id: str,
    use_case: GetSaldoUseCase = Depends(get_saldo_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET saldo/{cuenta_id}", x_caller_name)
    try:
        return use_case.execute(cuenta_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{cuenta_id}/movimientos")
def get_movimientos(
    cuenta_id: str,
    limit: int = 10,
    use_case: GetMovimientosUseCase = Depends(get_movimientos_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET movimientos/{cuenta_id}?limit={limit}", x_caller_name)
    try:
        return use_case.execute(cuenta_id, limit)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{cliente_id}")
def get_cuentas(
    cliente_id: str,
    use_case: GetCuentasUseCase = Depends(get_cuentas_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET cuentas/{cliente_id}", x_caller_name)
    try:
        return use_case.execute(cliente_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.post("", status_code=201)
def crear_cuenta(
    body: CrearCuentaRequest,
    use_case: CrearCuentaUseCase = Depends(get_crear_cuenta_uc),
    x_caller_name: str = Header("system"),
):
    _log("POST cuenta", x_caller_name)
    try:
        return use_case.execute(body.cliente_id, body.tipo, body.moneda)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e
