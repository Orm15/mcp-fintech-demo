import uuid
from datetime import datetime

import psycopg2.extras
from domain.entities.transferencia import LimiteTransferencia, Transferencia
from domain.exceptions import DomainValidationError
from infrastructure.database import get_conn


class PostgresTransferenciaRepository:
    def get_by_id(self, transfer_id: str) -> Transferencia | None:
        with (
            get_conn() as conn,
            conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur,
        ):
            cur.execute(
                "SELECT id, origen, destino, monto::float, moneda, descripcion, estado, "
                "TO_CHAR(fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha, motivo_fallo "
                "FROM transferencias WHERE id = %s",
                (transfer_id,),
            )
            row = cur.fetchone()
            return Transferencia(**row) if row else None

    def get_by_cuenta(self, cuenta_id: str) -> list[Transferencia]:
        with (
            get_conn() as conn,
            conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur,
        ):
            cur.execute(
                "SELECT id, origen, destino, monto::float, moneda, descripcion, estado, "
                "TO_CHAR(fecha, 'YYYY-MM-DD HH24:MI:SS') AS fecha, motivo_fallo "
                "FROM transferencias WHERE origen = %s OR destino = %s "
                "ORDER BY fecha DESC",
                (cuenta_id, cuenta_id),
            )
            return [Transferencia(**r) for r in cur.fetchall()]

    def get_limites(self, cliente_id: str) -> LimiteTransferencia | None:
        with (
            get_conn() as conn,
            conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur,
        ):
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
        """Crea una transferencia atómicamente: lock pesimista de ambas cuentas + valida
        saldo + actualiza saldos + inserta el registro. `get_conn()` envuelve todo en
        una transacción (commit on success, rollback on exception)."""
        if origen == destino:
            raise DomainValidationError("Cuenta origen y destino deben ser distintas")
        trf_id = f"TRF-{str(uuid.uuid4())[:6].upper()}"
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with get_conn() as conn, conn.cursor() as cur:
                # Lock pesimista de origen + validación de saldo
                cur.execute(
                    "SELECT saldo::float FROM cuentas WHERE id = %s FOR UPDATE",
                    (origen,),
                )
                row = cur.fetchone()
                if not row:
                    raise DomainValidationError(f"Cuenta origen '{origen}' no existe")
                if row[0] < monto:
                    raise DomainValidationError(
                        f"Saldo insuficiente en {origen}: {row[0]:.2f} < {monto:.2f}"
                    )
                # Verifica que destino exista y lockéalo también (mismo orden de lock
                # podría ser más robusto contra deadlocks, pero suficiente para el demo).
                cur.execute("SELECT 1 FROM cuentas WHERE id = %s FOR UPDATE", (destino,))
                if cur.fetchone() is None:
                    raise DomainValidationError(f"Cuenta destino '{destino}' no existe")
                # Actualiza saldos
                cur.execute(
                    "UPDATE cuentas SET saldo = saldo - %s WHERE id = %s",
                    (monto, origen),
                )
                cur.execute(
                    "UPDATE cuentas SET saldo = saldo + %s WHERE id = %s",
                    (monto, destino),
                )
                # Registra la transferencia
                cur.execute(
                    "INSERT INTO transferencias "
                    "(id, origen, destino, monto, moneda, descripcion, estado, fecha) "
                    "VALUES (%s, %s, %s, %s, 'PEN', %s, 'COMPLETADA', %s)",
                    (trf_id, origen, destino, monto, descripcion, fecha),
                )
        except psycopg2.errors.ForeignKeyViolation as e:
            raise DomainValidationError("Cuenta origen o destino no existe") from e
        return Transferencia(
            id=trf_id,
            origen=origen,
            destino=destino,
            monto=monto,
            moneda="PEN",
            descripcion=descripcion,
            estado="COMPLETADA",
            fecha=fecha,
        )
