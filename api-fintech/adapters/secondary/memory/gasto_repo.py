from domain.entities.gasto import CategoriaGasto, DatosGasto

_GASTOS: dict[str, dict] = {
    "cliente-001": {
        "mes": "2024-11",
        "categorias": {
            "Alimentación": {"gastado": 320.50, "transacciones": 3},
            "Entretenimiento": {"gastado": 325.90, "transacciones": 2},
            "Transporte": {"gastado": 150.00, "transacciones": 1},
            "Salud": {"gastado": 89.00, "transacciones": 1},
        },
    },
    "cliente-002": {
        "mes": "2024-11",
        "categorias": {
            "Alimentación": {"gastado": 210.00, "transacciones": 2},
            "Servicios": {"gastado": 205.00, "transacciones": 2},
            "Entretenimiento": {"gastado": 0.00, "transacciones": 0},
        },
    },
    "cliente-003": {
        "mes": "2024-11",
        "categorias": {
            "Alimentación": {"gastado": 450.00, "transacciones": 1},
            "Educación": {"gastado": 1200.00, "transacciones": 1},
            "Transporte": {"gastado": 200.00, "transacciones": 1},
            "Salud": {"gastado": 350.00, "transacciones": 1},
        },
    },
}
_PRESUPUESTOS_SEED: dict[str, dict[str, float]] = {
    "cliente-001": {"Alimentación": 400.00, "Entretenimiento": 200.00, "Transporte": 300.00},
    "cliente-002": {"Alimentación": 300.00, "Servicios": 250.00},
    "cliente-003": {"Alimentación": 500.00, "Educación": 1000.00, "Salud": 300.00},
}


class InMemoryGastoRepository:
    def __init__(self) -> None:
        self._presupuestos: dict[str, dict[str, float]] = {k: dict(v) for k, v in _PRESUPUESTOS_SEED.items()}

    def get_datos(self, cliente_id: str) -> DatosGasto | None:
        raw = _GASTOS.get(cliente_id)
        if raw is None:
            return None
        return DatosGasto(
            mes=raw["mes"],
            categorias={k: CategoriaGasto(**v) for k, v in raw["categorias"].items()},
        )

    def get_presupuestos(self, cliente_id: str) -> dict[str, float]:
        return self._presupuestos.get(cliente_id, {})

    def set_presupuesto(self, cliente_id: str, categoria: str, monto: float) -> None:
        self._presupuestos.setdefault(cliente_id, {})[categoria] = monto
