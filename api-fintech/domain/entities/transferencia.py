from pydantic import BaseModel


class Transferencia(BaseModel):
    id: str
    origen: str
    destino: str
    monto: float
    moneda: str
    descripcion: str
    estado: str
    fecha: str
    motivo_fallo: str | None = None


class LimiteTransferencia(BaseModel):
    limite_diario: float
    usado_hoy: float
    moneda: str
    disponible_hoy: float
    cliente_id: str
