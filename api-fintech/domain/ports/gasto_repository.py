from typing import Protocol, runtime_checkable

from domain.entities.gasto import DatosGasto


@runtime_checkable
class IGastoRepository(Protocol):
    def get_datos(self, cliente_id: str) -> DatosGasto | None: ...
    def get_presupuestos(self, cliente_id: str) -> dict[str, float]: ...
    def set_presupuesto(self, cliente_id: str, categoria: str, monto: float) -> None: ...
