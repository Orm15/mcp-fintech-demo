import uuid
from datetime import datetime

import psycopg2.extras

from domain.entities.transferencia import LimiteTransferencia, Transferencia
from domain.exceptions import DomainValidationError
from infrastructure.database import get_conn


class PostgresTransferenciaRepository:
    def get_by_id(self, transfer_id: str) -> Transferencia | None:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, origen, destino, monto::float, moneda, descripcion, estado, "
                    "TO_CHAR(fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha, motivo_fallo "
                    "FROM transferencias WHERE id = %s",
                    (transfer_id,),
                )
                row = cur.fetchone()
                return Transferencia(**row) if row else None

    def get_by_cuenta(self, cuenta_id: str) -> list[Transferencia]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, origen, destino, monto::float, moneda, descripcion, estado, "
                    "TO_CHAR(fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha, motivo_fallo "
                    "FROM transferencias WHERE origen = %s OR destino = %s "
                    "ORDER BY fecha DESC",
                    (cuenta_id, cuenta_id),
                )
                return [Transferencia(**r) for r in cur.fetchall()]

    def get_limites(self, cliente_id: str) -> LimiteTransferencia | None:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT limite_diario::float, usado_hoy::float, moneda "
                    "FROM limites_transferencia WHERE cliente_id = %s",
                    (cliente_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return LimiteTransferencia(
                    **row,
                    disponible_hoy=row["limite_diario"] - row["usado_hoy"],
                    cliente_id=cliente_id,
                )

    def crear(self, origen: str, destino: str, monto: float, descripcion: str) -> Transferencia:
        trf_id = f"TRF-{str(uuid.uuid4())[:6].upper()}"
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO transferencias "
                        "(id, origen, destino, monto, moneda, descripcion, estado, fecha) "
                        "VALUES (%s, %s, %s, %s, 'PEN', %s, 'COMPLETADA', %s)",
                        (trf_id, origen, destino, monto, descripcion, fecha),
                    )
        except psycopg2.errors.ForeignKeyViolation:
            raise DomainValidationError("Cuenta origen o destino no existe")
        return Transferencia(
            id=trf_id, origen=origen, destino=destino, monto=monto,
            moneda="PEN", descripcion=descripcion, estado="COMPLETADA", fecha=fecha,
        )
