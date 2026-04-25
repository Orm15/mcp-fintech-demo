from application.use_cases.transferencias import (
    CrearTransferenciaUseCase,
    GetHistorialUseCase,
    GetLimitesUseCase,
    GetTransferenciaUseCase,
)
from domain.exceptions import NotFoundError
from fastapi import APIRouter, Depends, Header, HTTPException
from infrastructure.container import (
    get_crear_transferencia_uc,
    get_historial_uc,
    get_limites_uc,
    get_transferencia_uc,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/transferencias", tags=["transferencias"])


class CrearTransferenciaRequest(BaseModel):
    origen: str
    destino: str
    monto: float = Field(gt=0)
    descripcion: str = ""


def _log(msg: str, caller: str) -> None:
    print(f"[transferencias] {msg} | caller={caller}", flush=True)


@router.post("", status_code=201)
def crear_transferencia(
    body: CrearTransferenciaRequest,
    use_case: CrearTransferenciaUseCase = Depends(get_crear_transferencia_uc),
    x_caller_name: str = Header("system"),
):
    _log("POST transferencia", x_caller_name)
    return use_case.execute(body.origen, body.destino, body.monto, body.descripcion)


# Specific paths before /{transfer_id} to avoid route shadowing
@router.get("/historial/{cuenta_id}")
def get_historial(
    cuenta_id: str,
    use_case: GetHistorialUseCase = Depends(get_historial_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET historial/{cuenta_id}", x_caller_name)
    return use_case.execute(cuenta_id)


@router.get("/limites/{cliente_id}")
def get_limites(
    cliente_id: str,
    use_case: GetLimitesUseCase = Depends(get_limites_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET limites/{cliente_id}", x_caller_name)
    try:
        return use_case.execute(cliente_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{transfer_id}")
def get_transferencia(
    transfer_id: str,
    use_case: GetTransferenciaUseCase = Depends(get_transferencia_uc),
    x_caller_name: str = Header("system"),
):
    _log(f"GET transferencia/{transfer_id}", x_caller_name)
    try:
        return use_case.execute(transfer_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e)) from e
