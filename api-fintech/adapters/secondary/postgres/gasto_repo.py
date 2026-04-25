import psycopg2.extras

from domain.entities.gasto import CategoriaGasto, DatosGasto
from infrastructure.database import get_conn


class PostgresGastoRepository:
    def get_datos(self, cliente_id: str) -> DatosGasto | None:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT mes, categoria, gastado::float, transacciones "
                    "FROM gastos_categorias WHERE cliente_id = %s ORDER BY categoria",
                    (cliente_id,),
                )
                rows = cur.fetchall()
                if not rows:
                    return None
                return DatosGasto(
                    mes=rows[0]["mes"],
                    categorias={
                        r["categoria"]: CategoriaGasto(gastado=r["gastado"], transacciones=r["transacciones"])
                        for r in rows
                    },
                )

    def get_presupuestos(self, cliente_id: str) -> dict[str, float]:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT categoria, monto::float FROM presupuestos WHERE cliente_id = %s",
                    (cliente_id,),
                )
                return {r["categoria"]: r["monto"] for r in cur.fetchall()}

    def set_presupuesto(self, cliente_id: str, categoria: str, monto: float) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO presupuestos (cliente_id, categoria, monto) VALUES (%s, %s, %s) "
                    "ON CONFLICT (cliente_id, categoria) DO UPDATE SET monto = EXCLUDED.monto",
                    (cliente_id, categoria, monto),
                )
