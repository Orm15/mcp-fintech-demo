from domain.exceptions import NotFoundError
from domain.ports.gasto_repository import IGastoRepository


class GetResumenUseCase:
    def __init__(self, repo: IGastoRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str) -> dict:
        datos = self._repo.get_datos(cliente_id)
        if datos is None:
            raise NotFoundError("Cliente no encontrado")
        total = round(sum(c.gastado for c in datos.categorias.values()), 2)
        return {
            "cliente_id": cliente_id,
            "mes": datos.mes,
            "total_gastado": total,
            "por_categoria": {k: v.model_dump() for k, v in datos.categorias.items()},
        }


class GetCategoriasUseCase:
    def __init__(self, repo: IGastoRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str) -> dict:
        datos = self._repo.get_datos(cliente_id)
        if datos is None:
            raise NotFoundError("Cliente no encontrado")
        presups = self._repo.get_presupuestos(cliente_id)
        categorias = {
            cat: {
                **d.model_dump(),
                "presupuesto": presups.get(cat),
                "excedido": (d.gastado > presups[cat]) if cat in presups else None,
            }
            for cat, d in datos.categorias.items()
        }
        return {"cliente_id": cliente_id, "categorias": categorias}


class SetPresupuestoUseCase:
    def __init__(self, repo: IGastoRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str, categoria: str, monto: float) -> dict:
        self._repo.set_presupuesto(cliente_id, categoria, monto)
        return {
            "mensaje": "Presupuesto actualizado",
            "cliente_id": cliente_id,
            "categoria": categoria,
            "monto": monto,
        }


class GetAlertasUseCase:
    def __init__(self, repo: IGastoRepository) -> None:
        self._repo = repo

    def execute(self, cliente_id: str) -> dict:
        datos = self._repo.get_datos(cliente_id)
        if datos is None:
            raise NotFoundError("Cliente no encontrado")
        presups = self._repo.get_presupuestos(cliente_id)
        alertas = [
            {
                "categoria": cat,
                "gastado": d.gastado,
                "presupuesto": presups[cat],
                "exceso": round(d.gastado - presups[cat], 2),
                "pct_excedido": round((d.gastado - presups[cat]) / presups[cat] * 100, 1),
            }
            for cat, d in datos.categorias.items()
            if cat in presups and d.gastado > presups[cat]
        ]
        return {"cliente_id": cliente_id, "total_alertas": len(alertas), "alertas": alertas}
