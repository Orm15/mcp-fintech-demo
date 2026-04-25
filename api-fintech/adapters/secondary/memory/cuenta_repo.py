import uuid

from domain.entities.cuenta import Cliente, Cuenta, Movimiento

_CUENTAS: dict[str, dict] = {
    "CTA-001": {
        "id": "CTA-001",
        "cliente_id": "cliente-001",
        "tipo": "ahorros",
        "moneda": "PEN",
        "saldo": 15420.50,
        "estado": "activa",
        "fecha_apertura": "2021-03-15",
    },
    "CTA-002": {
        "id": "CTA-002",
        "cliente_id": "cliente-001",
        "tipo": "corriente",
        "moneda": "USD",
        "saldo": 3200.00,
        "estado": "activa",
        "fecha_apertura": "2022-01-10",
    },
    "CTA-003": {
        "id": "CTA-003",
        "cliente_id": "cliente-002",
        "tipo": "ahorros",
        "moneda": "PEN",
        "saldo": 8750.00,
        "estado": "activa",
        "fecha_apertura": "2020-07-22",
    },
    "CTA-004": {
        "id": "CTA-004",
        "cliente_id": "cliente-003",
        "tipo": "ahorros",
        "moneda": "PEN",
        "saldo": 22100.00,
        "estado": "activa",
        "fecha_apertura": "2019-11-05",
    },
    "CTA-005": {
        "id": "CTA-005",
        "cliente_id": "cliente-003",
        "tipo": "corriente",
        "moneda": "PEN",
        "saldo": 5500.00,
        "estado": "activa",
        "fecha_apertura": "2020-02-18",
    },
    "CTA-006": {
        "id": "CTA-006",
        "cliente_id": "cliente-003",
        "tipo": "empresarial",
        "moneda": "PEN",
        "saldo": 98000.00,
        "estado": "activa",
        "fecha_apertura": "2023-05-01",
    },
}
_CLIENTES: dict[str, dict] = {
    "cliente-001": {"nombre": "María García", "cuentas": ["CTA-001", "CTA-002"]},
    "cliente-002": {"nombre": "Carlos López", "cuentas": ["CTA-003"]},
    "cliente-003": {"nombre": "Ana Torres", "cuentas": ["CTA-004", "CTA-005", "CTA-006"]},
}
_MOVIMIENTOS: dict[str, list[dict]] = {
    "CTA-001": [
        {
            "fecha": "2024-11-28",
            "descripcion": "Depósito sueldo noviembre",
            "monto": 4500.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-25", "descripcion": "Supermercado Wong", "monto": -320.50, "tipo": "debito"},
        {"fecha": "2024-11-22", "descripcion": "Netflix", "monto": -45.90, "tipo": "debito"},
        {
            "fecha": "2024-11-20",
            "descripcion": "Restaurante Astrid y Gastón",
            "monto": -280.00,
            "tipo": "debito",
        },
        {
            "fecha": "2024-11-15",
            "descripcion": "Transferencia recibida CTA-003",
            "monto": 500.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-10", "descripcion": "Farmacia InkaFarma", "monto": -89.00, "tipo": "debito"},
        {"fecha": "2024-11-05", "descripcion": "Gasolina Primax", "monto": -150.00, "tipo": "debito"},
    ],
    "CTA-002": [
        {"fecha": "2024-11-20", "descripcion": "Amazon.com purchase", "monto": -89.99, "tipo": "debito"},
        {
            "fecha": "2024-11-15",
            "descripcion": "Transferencia internacional recibida",
            "monto": 500.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-10", "descripcion": "Spotify Premium", "monto": -9.99, "tipo": "debito"},
    ],
    "CTA-003": [
        {
            "fecha": "2024-11-28",
            "descripcion": "Depósito sueldo noviembre",
            "monto": 3200.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-25", "descripcion": "Supermercado Plaza Vea", "monto": -210.00, "tipo": "debito"},
        {
            "fecha": "2024-11-20",
            "descripcion": "Transferencia enviada CTA-001",
            "monto": -500.00,
            "tipo": "debito",
        },
        {"fecha": "2024-11-15", "descripcion": "Recibo agua Sedapal", "monto": -85.00, "tipo": "debito"},
        {"fecha": "2024-11-10", "descripcion": "Recibo luz Enel", "monto": -120.00, "tipo": "debito"},
    ],
    "CTA-004": [
        {
            "fecha": "2024-11-28",
            "descripcion": "Depósito sueldo noviembre",
            "monto": 8500.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-25", "descripcion": "Supermercado Vivanda", "monto": -450.00, "tipo": "debito"},
        {"fecha": "2024-11-22", "descripcion": "Colegio mensualidad", "monto": -1200.00, "tipo": "debito"},
        {"fecha": "2024-11-18", "descripcion": "Combustible", "monto": -200.00, "tipo": "debito"},
        {"fecha": "2024-11-10", "descripcion": "Médico particular", "monto": -350.00, "tipo": "debito"},
    ],
    "CTA-005": [
        {
            "fecha": "2024-11-26",
            "descripcion": "Pago proveedor servicios",
            "monto": -2000.00,
            "tipo": "debito",
        },
        {"fecha": "2024-11-20", "descripcion": "Cobro honorarios", "monto": 3500.00, "tipo": "credito"},
    ],
    "CTA-006": [
        {
            "fecha": "2024-11-28",
            "descripcion": "Ingreso ventas semana 4",
            "monto": 25000.00,
            "tipo": "credito",
        },
        {
            "fecha": "2024-11-21",
            "descripcion": "Ingreso ventas semana 3",
            "monto": 18000.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-18", "descripcion": "Pago planilla", "monto": -15000.00, "tipo": "debito"},
        {
            "fecha": "2024-11-14",
            "descripcion": "Ingreso ventas semana 2",
            "monto": 22000.00,
            "tipo": "credito",
        },
        {"fecha": "2024-11-10", "descripcion": "Alquiler oficina", "monto": -3500.00, "tipo": "debito"},
    ],
}


class InMemoryCuentaRepository:
    def __init__(self) -> None:
        self._cuentas: dict[str, Cuenta] = {k: Cuenta(**v) for k, v in _CUENTAS.items()}
        self._clientes: dict[str, Cliente] = {k: Cliente(**v) for k, v in _CLIENTES.items()}

    def get_cliente(self, cliente_id: str) -> Cliente | None:
        return self._clientes.get(cliente_id)

    def get_cuenta(self, cuenta_id: str) -> Cuenta | None:
        return self._cuentas.get(cuenta_id)

    def get_movimientos(self, cuenta_id: str, limit: int) -> list[Movimiento]:
        return [Movimiento(**m) for m in _MOVIMIENTOS.get(cuenta_id, [])[:limit]]

    def crear_cuenta(self, cliente_id: str, tipo: str, moneda: str) -> Cuenta:
        nueva_id = f"CTA-{str(uuid.uuid4())[:6].upper()}"
        cuenta = Cuenta(
            id=nueva_id,
            cliente_id=cliente_id,
            tipo=tipo,
            moneda=moneda,
            saldo=0.0,
            estado="activa",
            fecha_apertura="2024-11-28",
        )
        self._cuentas[nueva_id] = cuenta
        self._clientes[cliente_id].cuentas.append(nueva_id)
        return cuenta
