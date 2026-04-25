from pydantic import BaseModel


class CategoriaGasto(BaseModel):
    gastado: float
    transacciones: int


class DatosGasto(BaseModel):
    mes: str
    categorias: dict[str, CategoriaGasto]
