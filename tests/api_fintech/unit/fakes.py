"""In-memory fake repos that satisfy the domain ports — used in unit tests."""

from __future__ import annotations

from datetime import date

from domain.entities.cuenta import Cliente, Cuenta, Movimiento
from domain.entities.gasto import CategoriaGasto, DatosGasto
from domain.entities.transferencia import LimiteTransferencia, Transferencia
from domain.exceptions import DomainValidationError


class FakeCuentaRepo:
    def __init__(self) -> None:
        self.clientes: dict[str, Cliente] = {}
        self.cuentas: dict[str, Cuenta] = {}
        self.movimientos: dict[str, list[Movimiento]] = {}

    def get_cliente(self, cliente_id: str) -> Cliente | None:
        return self.clientes.get(cliente_id)

    def get_cuenta(self, cuenta_id: str) -> Cuenta | None:
        return self.cuentas.get(cuenta_id)

    def get_movimientos(self, cuenta_id: str, limit: int) -> list[Movimiento]:
        return self.movimientos.get(cuenta_id, [])[:limit]

    def crear_cuenta(self, cliente_id: str, tipo: str, moneda: str) -> Cuenta:
        if cliente_id not in self.clientes:
            raise DomainValidationError(f"Cliente '{cliente_id}' no existe")
        new_id = f"CTA-FAKE{len(self.cuentas) + 1:03d}"
        c = Cuenta(
            id=new_id,
            cliente_id=cliente_id,
            tipo=tipo,
            moneda=moneda,
            saldo=0.0,
            estado="activa",
            fecha_apertura=str(date.today()),
        )
        self.cuentas[new_id] = c
        self.clientes[cliente_id].cuentas.append(new_id)
        return c


class FakeTransferenciaRepo:
    def __init__(self) -> None:
        self.transferencias: dict[str, Transferencia] = {}
        self.limites: dict[str, LimiteTransferencia] = {}

    def get_by_id(self, transfer_id: str) -> Transferencia | None:
        return self.transferencias.get(transfer_id)

    def get_by_cuenta(self, cuenta_id: str) -> list[Transferencia]:
        return [t for t in self.transferencias.values() if t.origen == cuenta_id or t.destino == cuenta_id]

    def get_limites(self, cliente_id: str) -> LimiteTransferencia | None:
        return self.limites.get(cliente_id)

    def crear(self, origen: str, destino: str, monto: float, descripcion: str) -> Transferencia:
        new_id = f"TRF-FAKE{len(self.transferencias) + 1:03d}"
        t = Transferencia(
            id=new_id,
            origen=origen,
            destino=destino,
            monto=monto,
            moneda="PEN",
            descripcion=descripcion,
            estado="COMPLETADA",
            fecha="2026-04-25 00:00:00",
            motivo_fallo=None,
        )
        self.transferencias[new_id] = t
        return t


class FakeGastoRepo:
    def __init__(self) -> None:
        self.datos: dict[str, DatosGasto] = {}
        self.presupuestos: dict[str, dict[str, float]] = {}

    def get_datos(self, cliente_id: str) -> DatosGasto | None:
        return self.datos.get(cliente_id)

    def get_presupuestos(self, cliente_id: str) -> dict[str, float]:
        return self.presupuestos.get(cliente_id, {})

    def set_presupuesto(self, cliente_id: str, categoria: str, monto: float) -> None:
        self.presupuestos.setdefault(cliente_id, {})[categoria] = monto


def seed_cliente_con_cuenta(repo: FakeCuentaRepo, cliente_id: str = "cliente-001") -> None:
    """Seed mínimo: 1 cliente, 1 cuenta con saldo, 2 movimientos."""
    repo.clientes[cliente_id] = Cliente(nombre="Test User", cuentas=["CTA-T01"])
    repo.cuentas["CTA-T01"] = Cuenta(
        id="CTA-T01",
        cliente_id=cliente_id,
        tipo="ahorros",
        moneda="PEN",
        saldo=1000.0,
        estado="activa",
        fecha_apertura="2026-01-01",
    )
    repo.movimientos["CTA-T01"] = [
        Movimiento(fecha="2026-04-20", descripcion="depósito", monto=500.0, tipo="credito"),
        Movimiento(fecha="2026-04-22", descripcion="compra", monto=120.0, tipo="debito"),
    ]


def seed_gastos(repo: FakeGastoRepo, cliente_id: str = "cliente-001") -> None:
    repo.datos[cliente_id] = DatosGasto(
        mes="2026-04",
        categorias={
            "Alimentación": CategoriaGasto(gastado=400.0, transacciones=10),
            "Transporte": CategoriaGasto(gastado=180.0, transacciones=5),
        },
    )
    repo.presupuestos[cliente_id] = {"Alimentación": 350.0, "Transporte": 200.0}
