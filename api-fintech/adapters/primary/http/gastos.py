from application.use_cases.gastos import (
    GetAlertasUseCase,
    GetCategoriasUseCase,
    GetResumenUseCase,
    SetPresupuestoUseCase,
)
from domain.exceptions import NotFoundError
from fastapi import APIRouter, Depends, Header, HTTPException
from infrastructure.container import (
    get_alertas_uc,
    get_categorias_uc,
    get_resumen_uc,
    get_set_presupuesto_uc,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/gastos", tags=["gastos"])


class SetPresupuestoRequest(BaseModel):
    cliente_id: str
    categoria: str
    monto: float = Field(gt=0)


def _log(msg: str, caller: str) -> None:
    print(f"[gastos] {msg} | caller={caller}", flush=True)


@router.get("/{cliente_id}/resumen")
def get_resumen(
    cliente_id: str,
    use_case: GetResumenUseCase = Depends(get_resumen_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET resumen/{cliente_id}", x_caller_name)
    try:
        return use_case.execute(cliente_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{cliente_id}/categorias")
def get_categorias(
    cliente_id: str,
    use_case: GetCategoriasUseCase = Depends(get_categorias_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET categorias/{cliente_id}", x_caller_name)
    try:
        return use_case.execute(cliente_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{cliente_id}/alertas")
def get_alertas(
    cliente_id: str,
    use_case: GetAlertasUseCase = Depends(get_alertas_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET alertas/{cliente_id}", x_caller_name)
    try:
        return use_case.execute(cliente_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/presupuesto", status_code=201)
def set_presupuesto(
    body: SetPresupuestoRequest,
    use_case: SetPresupuestoUseCase = Depends(get_set_presupuesto_uc),
    x_caller_name: str = Header("system"),
):
    _log("POST presupuesto", x_caller_name)
    return use_case.execute(body.cliente_id, body.categoria, body.monto)
