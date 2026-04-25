from domain.exceptions import NotFoundError
from domain.ports.cuenta_repository import ICuentaRepository


class GetCuentasUseCase:
    def __init__(self, repo: ICuentaRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str) -> dict:
        cliente = self._repo.get_cliente(cliente_id)
        if not cliente:
            raise NotFoundError(f"Cliente '{cliente_id}' no existe")
        cuentas = [self._repo.get_cuenta(cid) for cid in cliente.cuentas]
        return {
            "cliente_id": cliente_id,
            "nombre": cliente.nombre,
            "cuentas": [c.model_dump() for c in cuentas if c],
        }


class GetSaldoUseCase:
    def __init__(self, repo: ICuentaRepository) -> None:
        self._repo = repo

    def execute(self, cuenta_id: str) -> dict:
        cuenta = self._repo.get_cuenta(cuenta_id)
        if not cuenta:
            raise NotFoundError("Cuenta no encontrada")
        return {
            "cuenta_id": cuenta_id,
            "saldo": cuenta.saldo,
            "moneda": cuenta.moneda,
            "tipo": cuenta.tipo,
        }


class GetMovimientosUseCase:
    def __init__(self, repo: ICuentaRepository) -> None:
        self._repo = repo

    def execute(self, cuenta_id: str, limit: int) -> dict:
        if not self._repo.get_cuenta(cuenta_id):
            raise NotFoundError("Cuenta no encontrada")
        movs = self._repo.get_movimientos(cuenta_id, limit)
        return {
            "cuenta_id": cuenta_id,
            "movimientos": [m.model_dump() for m in movs],
            "total": len(movs),
        }


class CrearCuentaUseCase:
    def __init__(self, repo: ICuentaRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str, tipo: str, moneda: str) -> dict:
        if not self._repo.get_cliente(cliente_id):
            raise NotFoundError("Cliente no encontrado")
        cuenta = self._repo.crear_cuenta(cliente_id, tipo, moneda)
        return {"mensaje": "Cuenta creada", "cuenta": cuenta.model_dump()}
