from typing import Literal

from pydantic import BaseModel


class Movimiento(BaseModel):
    fecha: str
    descripcion: str
    monto: float
    tipo: Literal["credito", "debito"]


class Cuenta(BaseModel):
    id: str
    cliente_id: str
    tipo: str
    moneda: str
    saldo: float
    estado: str
    fecha_apertura: str


class Cliente(BaseModel):
    nombre: str
    cuentas: list[str]
