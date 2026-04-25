import uuid
from datetime import date

import psycopg2.extras

from domain.entities.cuenta import Cliente, Cuenta, Movimiento
from domain.exceptions import DomainValidationError
from infrastructure.database import get_conn


class PostgresCuentaRepository:
    def get_cliente(self, cliente_id: str) -> Cliente | None:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT nombre FROM clientes WHERE id = %s", (cliente_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    "SELECT id FROM cuentas WHERE cliente_id = %s ORDER BY fecha_apertura",
                    (cliente_id,),
                )
                return Cliente(nombre=row["nombre"], cuentas=[r["id"] for r in cur.fetchall()])

    def get_cuenta(self, cuenta_id: str) -> Cuenta | None:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, cliente_id, tipo, moneda, saldo::float, estado, fecha_apertura::text "
                    "FROM cuentas WHERE id = %s",
                    (cuenta_id,),
                )
                row = cur.fetchone()
                return Cuenta(**row) if row else None

    def get_movimientos(self, cuenta_id: str, limit: int) -> list[Movimiento]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT fecha::text, descripcion, monto::float, tipo "
                    "FROM movimientos WHERE cuenta_id = %s "
                    "ORDER BY fecha DESC, creado_en DESC LIMIT %s",
                    (cuenta_id, limit),
                )
                return [Movimiento(**r) for r in cur.fetchall()]

    def crear_cuenta(self, cliente_id: str, tipo: str, moneda: str) -> Cuenta:
        nueva_id = f"CTA-{str(uuid.uuid4())[:6].upper()}"
        hoy = date.today().isoformat()
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO cuentas (id, cliente_id, tipo, moneda, saldo, estado, fecha_apertura) "
                        "VALUES (%s, %s, %s, %s, 0, 'activa', %s)",
                        (nueva_id, cliente_id, tipo, moneda, hoy),
                    )
        except psycopg2.errors.ForeignKeyViolation:
            raise DomainValidationError(f"Cliente '{cliente_id}' no existe en la base de datos")
        return Cuenta(
            id=nueva_id, cliente_id=cliente_id, tipo=tipo, moneda=moneda,
            saldo=0.0, estado="activa", fecha_apertura=hoy,
        )
