import uuid
from datetime import datetime

from domain.entities.transferencia import LimiteTransferencia, Transferencia

_TRANSFERENCIAS: dict[str, dict] = {
    "TRF-001": {
        "id": "TRF-001",
        "origen": "CTA-001",
        "destino": "CTA-003",
        "monto": 500.00,
        "moneda": "PEN",
        "descripcion": "Pago deuda",
        "estado": "COMPLETADA",
        "fecha": "2024-11-15 14:32:00",
    },
    "TRF-002": {
        "id": "TRF-002",
        "origen": "CTA-004",
        "destino": "CTA-001",
        "monto": 1000.00,
        "moneda": "PEN",
        "descripcion": "Préstamo familiar",
        "estado": "COMPLETADA",
        "fecha": "2024-11-10 09:15:00",
    },
    "TRF-003": {
        "id": "TRF-003",
        "origen": "CTA-006",
        "destino": "CTA-005",
        "monto": 5000.00,
        "moneda": "PEN",
        "descripcion": "Traslado operativo",
        "estado": "PENDIENTE",
        "fecha": "2024-11-28 16:00:00",
    },
    "TRF-004": {
        "id": "TRF-004",
        "origen": "CTA-002",
        "destino": "CTA-001",
        "monto": 200.00,
        "moneda": "USD",
        "descripcion": "Conversión divisas",
        "estado": "FALLIDA",
        "fecha": "2024-11-20 11:22:00",
        "motivo_fallo": "Monedas incompatibles",
    },
}
_LIMITES: dict[str, dict] = {
    "cliente-001": {"limite_diario": 5000.00, "usado_hoy": 500.00, "moneda": "PEN"},
    "cliente-002": {"limite_diario": 3000.00, "usado_hoy": 0.00, "moneda": "PEN"},
    "cliente-003": {"limite_diario": 50000.00, "usado_hoy": 5000.00, "moneda": "PEN"},
}


class InMemoryTransferenciaRepository:
    def __init__(self) -> None:
        self._store: dict[str, Transferencia] = {k: Transferencia(**v) for k, v in _TRANSFERENCIAS.items()}

    def get_by_id(self, transfer_id: str) -> Transferencia | None:
        return self._store.get(transfer_id)

    def get_by_cuenta(self, cuenta_id: str) -> list[Transferencia]:
        return [t for t in self._store.values() if t.origen == cuenta_id or t.destino == cuenta_id]

    def get_limites(self, cliente_id: str) -> LimiteTransferencia | None:
        raw = _LIMITES.get(cliente_id)
        if raw is None:
            return None
        return LimiteTransferencia(
            **raw,
            disponible_hoy=raw["limite_diario"] - raw["usado_hoy"],
            cliente_id=cliente_id,
        )

    def crear(self, origen: str, destino: str, monto: float, descripcion: str) -> Transferencia:
        trf_id = f"TRF-{str(uuid.uuid4())[:6].upper()}"
        trf = Transferencia(
            id=trf_id,
            origen=origen,
            destino=destino,
            monto=monto,
            moneda="PEN",
            descripcion=descripcion,
            estado="COMPLETADA",
            fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._store[trf_id] = trf
        return trf
