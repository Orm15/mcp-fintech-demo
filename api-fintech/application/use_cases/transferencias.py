from domain.exceptions import NotFoundError
from domain.ports.transferencia_repository import ITransferenciaRepository


class CrearTransferenciaUseCase:
    def __init__(self, repo: ITransferenciaRepository) -> None:
        self._repo = repo

    def execute(self, origen: str, destino: str, monto: float, descripcion: str) -> dict:
        trf = self._repo.crear(origen, destino, monto, descripcion)
        return {"mensaje": "Transferencia ejecutada", "transferencia": trf.model_dump()}


class GetTransferenciaUseCase:
    def __init__(self, repo: ITransferenciaRepository) -> None:
        self._repo = repo

    def execute(self, transfer_id: str) -> dict:
        trf = self._repo.get_by_id(transfer_id)
        if not trf:
            raise NotFoundError("Transferencia no encontrada")
        return trf.model_dump()


class GetHistorialUseCase:
    def __init__(self, repo: ITransferenciaRepository) -> None:
        self._repo = repo

    def execute(self, cuenta_id: str) -> dict:
        trfs = self._repo.get_by_cuenta(cuenta_id)
        return {
            "cuenta_id": cuenta_id,
            "transferencias": [t.model_dump() for t in trfs],
            "total": len(trfs),
        }


class GetLimitesUseCase:
    def __init__(self, repo: ITransferenciaRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str) -> dict:
        limites = self._repo.get_limites(cliente_id)
        if not limites:
            raise NotFoundError("Cliente no encontrado")
        return limites.model_dump()
