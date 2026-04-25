import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

import asyncpg
import httpx
import structlog
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

# ── Config — structured logging (JSON) ────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(message)s")
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger("mcp-fintech")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fintech:fintech123@postgres:5432/fintechdb")
FUNCTION_BASE = os.getenv("FUNCTION_BASE_URL", "http://api-fintech:9000")
FUNCTION_KEY = os.getenv("FUNCTION_KEY", "dev-key")
MCP_SERVER_NAME = "fintech_mcp"

# ── Permisos por tool ─────────────────────────────────────────────────────────
TOOL_PERMISSIONS: dict[str, str] = {
    "fintech_consultar_cuentas": "cuentas:read",
    "fintech_ver_saldo": "cuentas:read",
    "fintech_ver_movimientos": "cuentas:read",
    "fintech_crear_cuenta": "cuentas:write",
    "fintech_realizar_transferencia": "transferencias:write",
    "fintech_estado_transferencia": "transferencias:read",
    "fintech_historial_transferencias": "transferencias:read",
    "fintech_consultar_limites": "transferencias:read",
    "fintech_resumen_gastos": "gastos:read",
    "fintech_detalle_categorias": "gastos:read",
    "fintech_establecer_presupuesto": "gastos:write",
    "fintech_ver_alertas": "gastos:read",
    "fintech_ver_auditoria": "cuentas:write",
    "fintech_resumen_gastos_html": "gastos:read",
    "fintech_consultar_cuentas_html": "cuentas:read",
    "fintech_ver_auditoria_html": "cuentas:write",
}

# ── Lifespan — pool de BD ─────────────────────────────────────────────────────
_SHARED_POOL: asyncpg.Pool | None = None
_POOL_LOCK = asyncio.Lock()


async def _get_or_create_pool() -> asyncpg.Pool:
    """Pool singleton compartido entre MCP sessions y /health (con doble-check + lock)."""
    global _SHARED_POOL
    if _SHARED_POOL is not None:
        return _SHARED_POOL
    async with _POOL_LOCK:
        if _SHARED_POOL is not None:
            return _SHARED_POOL
        for attempt in range(1, 6):
            try:
                _SHARED_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
                logger.info("postgres.pool.created", attempt=attempt)
                return _SHARED_POOL
            except Exception as e:
                logger.warning("postgres.pool.unavailable", attempt=attempt, total=5, error=str(e))
                if attempt < 5:
                    await asyncio.sleep(3)
        raise RuntimeError("No se pudo conectar a PostgreSQL tras 5 intentos")


@asynccontextmanager
async def app_lifespan(server):
    pool = await _get_or_create_pool()
    yield {"pool": pool}
    # No cerramos aquí — el pool es shared y se reutiliza entre sesiones MCP.


mcp = FastMCP(
    MCP_SERVER_NAME,
    instructions=(
        "MCP bancario Fintech. Tools disponibles:\n"
        "- Cuentas (read: user+admin / write: solo admin)\n"
        "- Transferencias (read+write: solo admin)\n"
        "- Gastos (read: user+admin / write: solo admin)\n"
        "- Auditoría: solo admin\n\n"
        "Keys de prueba:\n"
        "  user:  usr-maria-garcia-a3f9k2\n"
        "  admin: adm-fintech-x9p2m7k1"
    ),
    lifespan=app_lifespan,
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)


# ── Healthcheck — usado por docker-compose ───────────────────────────────────
@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health(_: Request) -> JSONResponse:
    """Liveness + readiness combinados. Inicializa el pool perezosamente al primer call."""
    try:
        pool = await _get_or_create_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return JSONResponse({"status": "ok", "service": "mcp-fintech", "tools": 16})
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)


# ── Auth + auditoría ──────────────────────────────────────────────────────────
def _get_api_key(ctx: Context) -> str:
    try:
        h = ctx.request_context.request.headers
        return h.get("x-api-key") or h.get("X-API-Key") or ""
    except Exception:
        return os.getenv("TEST_API_KEY", "")


def _fn_headers(nombre: str, uid: str) -> dict:
    return {
        "X-Functions-Key": FUNCTION_KEY,
        "Content-Type": "application/json",
        "X-Caller-Name": quote(nombre, safe=""),
        "X-Caller-User-Id": uid,
    }


async def _auth(pool: asyncpg.Pool, api_key: str, tool: str, params: dict) -> dict:
    """Valida key, verifica permiso, registra audit_log, actualiza rate limit."""
    if not api_key:
        raise PermissionError("401::API key requerida. Configura X-API-Key en Claude Desktop.")

    async with pool.acquire() as conn:
        consumer = await conn.fetchrow(
            "SELECT id, nombre, rol, permisos, rate_limit_hora, activo "
            "FROM api_consumers WHERE api_key = $1",
            api_key,
        )
        if not consumer:
            raise PermissionError("401::API key inválida")
        if not consumer["activo"]:
            raise PermissionError("403::Consumidor desactivado")

        ventana = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        counter = await conn.fetchrow(
            "SELECT total_llamadas FROM rate_limit_counter " "WHERE consumer_id = $1 AND ventana_hora = $2",
            consumer["id"],
            ventana,
        )
        if (counter["total_llamadas"] if counter else 0) >= consumer["rate_limit_hora"]:
            raise PermissionError(f"429::Rate limit: {consumer['rate_limit_hora']}/hora alcanzado")

        permiso_req = TOOL_PERMISSIONS.get(tool)
        permisos = json.loads(consumer["permisos"])
        if permiso_req and permiso_req not in permisos:
            await conn.execute(
                "INSERT INTO audit_log (consumer_id, mcp_server, tool_nombre, parametros, "
                "status_code, error_msg, latencia_ms) VALUES ($1,$2,$3,$4,403,$5,0)",
                consumer["id"],
                MCP_SERVER_NAME,
                tool,
                json.dumps(params),
                f"Sin permiso: requiere {permiso_req}",
            )
            raise PermissionError(
                f"403::Sin permiso para '{tool}'. Requiere: {permiso_req}. "
                f"Rol '{consumer['rol']}' tiene: {permisos}"
            )

        audit_id = await conn.fetchval(
            "INSERT INTO audit_log (consumer_id, mcp_server, tool_nombre, parametros) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            consumer["id"],
            MCP_SERVER_NAME,
            tool,
            json.dumps(params),
        )
        await conn.execute(
            "INSERT INTO rate_limit_counter (consumer_id, ventana_hora, total_llamadas) VALUES ($1,$2,1) "
            "ON CONFLICT (consumer_id, ventana_hora) "
            "DO UPDATE SET total_llamadas = rate_limit_counter.total_llamadas + 1, actualizado_en = NOW()",
            consumer["id"],
            ventana,
        )
        logger.info("tool.invoked", tool=tool, consumer=consumer["nombre"], rol=consumer["rol"])
        return {
            "audit_id": str(audit_id),
            "consumer": {"id": str(consumer["id"]), "nombre": consumer["nombre"], "rol": consumer["rol"]},
        }


async def _complete(pool: asyncpg.Pool, audit_id: str, status: int, ms: int, err: str = None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE audit_log SET status_code=$1, latencia_ms=$2, error_msg=$3 WHERE id=$4",
            status,
            ms,
            err,
            audit_id,
        )


async def _call(method: str, path: str, consumer: dict, query: dict = None, body: dict = None) -> Any:
    async with httpx.AsyncClient() as client:
        r = await client.request(
            method,
            f"{FUNCTION_BASE}{path}",
            params=query,
            json=body,
            headers=_fn_headers(consumer["nombre"], consumer["id"]),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()


async def _run(
    ctx: Context, tool: str, params: dict, method: str, path: str, query: dict = None, body: dict = None
) -> dict:
    """Helper DRY: auth → HTTP → audit completo."""
    key = _get_api_key(ctx)
    pool: asyncpg.Pool = ctx.request_context.lifespan_context["pool"]
    t0 = time.monotonic()
    auth = None
    try:
        auth = await _auth(pool, key, tool, params)
        result = await _call(method, path, auth["consumer"], query=query, body=body)
        ms = int((time.monotonic() - t0) * 1000)
        await _complete(pool, auth["audit_id"], 200, ms)
        return result
    except PermissionError as e:
        code, msg = str(e).split("::", 1)
        return {"error": msg, "status": int(code)}
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        if auth:
            await _complete(pool, auth["audit_id"], 502, ms, str(e))
        return {"error": str(e), "status": 502}


# ════════════════════════════════════════════════════════════════════════════
# TOOLS — CUENTAS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool(name="fintech_consultar_cuentas")
async def fintech_consultar_cuentas(
    cliente_id: Annotated[str, Field(description="ID del cliente (cliente-001, cliente-002, cliente-003)")],
    ctx: Context,
) -> dict:
    """Consulta todas las cuentas bancarias de un cliente con saldos actuales. Requiere: cuentas:read"""
    return await _run(
        ctx, "fintech_consultar_cuentas", {"cliente_id": cliente_id}, "GET", f"/api/cuentas/{cliente_id}"
    )


@mcp.tool(name="fintech_ver_saldo")
async def fintech_ver_saldo(
    cuenta_id: Annotated[str, Field(description="ID de la cuenta (CTA-001 al CTA-006)")],
    ctx: Context,
) -> dict:
    """Obtiene el saldo actual de una cuenta específica. Requiere: cuentas:read"""
    return await _run(
        ctx, "fintech_ver_saldo", {"cuenta_id": cuenta_id}, "GET", f"/api/cuentas/{cuenta_id}/saldo"
    )


@mcp.tool(name="fintech_ver_movimientos")
async def fintech_ver_movimientos(
    cuenta_id: Annotated[str, Field(description="ID de la cuenta")],
    ctx: Context,
    limit: Annotated[int, Field(ge=1, le=50, description="Número de movimientos a retornar (1-50)")] = 10,
) -> dict:
    """Retorna los últimos movimientos de una cuenta bancaria. Requiere: cuentas:read"""
    return await _run(
        ctx,
        "fintech_ver_movimientos",
        {"cuenta_id": cuenta_id, "limit": limit},
        "GET",
        f"/api/cuentas/{cuenta_id}/movimientos",
        query={"limit": limit},
    )


@mcp.tool(name="fintech_crear_cuenta")
async def fintech_crear_cuenta(
    cliente_id: Annotated[str, Field(description="ID del cliente")],
    tipo: Annotated[str, Field(description="Tipo de cuenta: ahorros | corriente | empresarial")],
    ctx: Context,
    moneda: Annotated[str, Field(description="Moneda: PEN | USD")] = "PEN",
) -> dict:
    """Crea una nueva cuenta bancaria para un cliente. Solo admins. Requiere: cuentas:write"""
    body = {"cliente_id": cliente_id, "tipo": tipo, "moneda": moneda}
    return await _run(ctx, "fintech_crear_cuenta", body, "POST", "/api/cuentas", body=body)


# ── Server-side HTML rendering — variante de comparación (cuentas) ───────────
def _render_consultar_cuentas_html(data: dict) -> str:
    """HTML auto-contenido con las cuentas de un cliente — estilo 'tarjeta bancaria'."""
    cliente_id = data.get("cliente_id", "?")
    nombre = data.get("nombre", "?")
    cuentas = data.get("cuentas", []) or []
    saldo_total = sum(float(c.get("saldo", 0) or 0) for c in cuentas)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    if cuentas:
        cards_list = []
        for c in cuentas:
            cuenta_id = c.get("id", "?")
            tipo = (c.get("tipo") or "?").capitalize()
            moneda = c.get("moneda", "?")
            saldo = float(c.get("saldo", 0) or 0)
            estado = c.get("estado", "?")
            estado_color = "#10b981" if estado == "activa" else "#f59e0b"
            cards_list.append(
                f'<div class="card">'
                f'<div class="card-head">'
                f'<span class="cuenta-id">{cuenta_id}</span>'
                f'<span class="estado" style="background:{estado_color}1f;color:{estado_color};">{estado}</span>'
                f"</div>"
                f'<div class="tipo">{tipo} · {moneda}</div>'
                f'<div class="saldo"><span class="value">{saldo:,.2f}</span>'
                f'<span class="moneda">{moneda}</span></div>'
                f"</div>"
            )
        cards_html = "".join(cards_list)
    else:
        cards_html = '<div class="empty">Este cliente no tiene cuentas registradas.</div>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Cuentas · {cliente_id}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         padding: 2rem; background: #f8fafc; color: #0f172a; margin: 0; }}
  .container {{ max-width: 760px; margin: 0 auto; background: white; border-radius: 12px;
                padding: 2rem; box-shadow: 0 4px 12px rgba(15,23,42,0.08); }}
  .badge {{ display: inline-block; background: #dbeafe; color: #1e40af; padding: 0.25rem 0.6rem;
            border-radius: 4px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em;
            text-transform: uppercase; }}
  h1 {{ margin: 0.5rem 0 0.25rem; color: #1e293b; font-size: 1.75rem; }}
  .meta {{ color: #64748b; font-size: 0.875rem; }}
  .total {{ background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%); color: white;
            padding: 1.5rem; border-radius: 8px; margin: 1.5rem 0; }}
  .total .label {{ opacity: 0.85; font-size: 0.7rem; text-transform: uppercase;
                   letter-spacing: 0.1em; }}
  .total .value {{ font-size: 2.5rem; font-weight: 700; margin-top: 0.25rem;
                   font-variant-numeric: tabular-nums; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
           gap: 1rem; margin-top: 1rem; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.25rem;
           background: linear-gradient(180deg, #ffffff, #f8fafc); }}
  .card-head {{ display: flex; justify-content: space-between; align-items: center; }}
  .cuenta-id {{ font-family: 'SF Mono', Menlo, monospace; font-size: 0.875rem;
                color: #475569; font-weight: 600; }}
  .estado {{ font-size: 0.65rem; padding: 0.15rem 0.5rem; border-radius: 999px;
             font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
  .tipo {{ color: #64748b; font-size: 0.75rem; margin-top: 0.5rem;
           text-transform: uppercase; letter-spacing: 0.05em; }}
  .saldo {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem;
            font-variant-numeric: tabular-nums; color: #0f172a; }}
  .saldo .moneda {{ font-size: 0.75rem; font-weight: 500; color: #64748b; margin-left: 0.4rem; }}
  .empty {{ text-align: center; color: #94a3b8; padding: 2rem; }}
  .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;
             color: #94a3b8; font-size: 0.75rem; line-height: 1.5; }}
  code {{ background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">
  <span class="badge">Server-rendered</span>
  <h1>Cuentas de {nombre}</h1>
  <div class="meta">Cliente <strong>{cliente_id}</strong> · {len(cuentas)} cuenta{'s' if len(cuentas) != 1 else ''}</div>
  <div class="total">
    <div class="label">Saldo total agregado</div>
    <div class="value">{saldo_total:,.2f} <span style="font-size:1rem;opacity:.7;">PEN</span></div>
  </div>
  <div class="grid">{cards_html}</div>
  <div class="footer">
    Generado server-side por <code>mcp-fintech</code> · {timestamp}<br>
    Comparalo con el dashboard React del prompt <code>resumen_cliente</code>
    para ver el contraste server-side vs LLM-generated.
  </div>
</div>
</body>
</html>"""


@mcp.tool(name="fintech_consultar_cuentas_html")
async def fintech_consultar_cuentas_html(
    cliente_id: Annotated[str, Field(description="ID del cliente (cliente-001, cliente-002, cliente-003)")],
    ctx: Context,
) -> dict:
    """Listado de cuentas PRE-RENDERIZADO en HTML por el server (no por Claude).

    Mostrá el campo `html` como artifact tipo `text/html` SIN modificarlo. Aclará al
    usuario que es render server-side, complementario al dashboard React del prompt
    `resumen_cliente`. Ambos enfoques resuelven el mismo caso de uso con tradeoffs distintos
    (determinismo vs interactividad).

    Requiere: cuentas:read
    """
    raw = await _run(
        ctx,
        "fintech_consultar_cuentas_html",
        {"cliente_id": cliente_id},
        "GET",
        f"/api/cuentas/{cliente_id}",
    )
    if "error" in raw:
        return raw
    return {
        "render_source": "server-side (Python f-string + CSS inline)",
        "render_format": "text/html",
        "instructions_for_assistant": (
            "Mostrá el campo `html` como artifact text/html SIN modificarlo. "
            "Recordale al usuario que este es render server-side; comparalo con el "
            "dashboard del prompt `resumen_cliente` que usa Artifact React generado por LLM."
        ),
        "data": raw,
        "html": _render_consultar_cuentas_html(raw),
    }


# ════════════════════════════════════════════════════════════════════════════
# TOOLS — TRANSFERENCIAS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool(name="fintech_realizar_transferencia")
async def fintech_realizar_transferencia(
    origen: Annotated[str, Field(description="ID cuenta origen (ej: CTA-001)")],
    destino: Annotated[str, Field(description="ID cuenta destino (ej: CTA-003)")],
    monto: Annotated[float, Field(gt=0, description="Monto a transferir (mayor que 0)")],
    ctx: Context,
    descripcion: Annotated[str, Field(description="Descripción opcional de la transferencia")] = "",
) -> dict:
    """Ejecuta una transferencia bancaria entre dos cuentas. Solo admins. Requiere: transferencias:write"""
    body = {"origen": origen, "destino": destino, "monto": monto, "descripcion": descripcion}
    return await _run(ctx, "fintech_realizar_transferencia", body, "POST", "/api/transferencias", body=body)


@mcp.tool(name="fintech_estado_transferencia")
async def fintech_estado_transferencia(
    transfer_id: Annotated[str, Field(description="ID de la transferencia (ej: TRF-001)")],
    ctx: Context,
) -> dict:
    """Estado de una transferencia: COMPLETADA | PENDIENTE | FALLIDA. Requiere: transferencias:read"""
    return await _run(
        ctx,
        "fintech_estado_transferencia",
        {"transfer_id": transfer_id},
        "GET",
        f"/api/transferencias/{transfer_id}",
    )


@mcp.tool(name="fintech_historial_transferencias")
async def fintech_historial_transferencias(
    cuenta_id: Annotated[str, Field(description="ID de la cuenta (enviadas y recibidas)")],
    ctx: Context,
) -> dict:
    """Historial de transferencias de una cuenta (enviadas y recibidas). Requiere: transferencias:read"""
    return await _run(
        ctx,
        "fintech_historial_transferencias",
        {"cuenta_id": cuenta_id},
        "GET",
        f"/api/transferencias/historial/{cuenta_id}",
    )


@mcp.tool(name="fintech_consultar_limites")
async def fintech_consultar_limites(
    cliente_id: Annotated[str, Field(description="ID del cliente")],
    ctx: Context,
) -> dict:
    """Límites diarios de transferencia y monto usado hoy. Requiere: transferencias:read"""
    return await _run(
        ctx,
        "fintech_consultar_limites",
        {"cliente_id": cliente_id},
        "GET",
        f"/api/transferencias/limites/{cliente_id}",
    )


# ════════════════════════════════════════════════════════════════════════════
# TOOLS — GASTOS
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool(name="fintech_resumen_gastos")
async def fintech_resumen_gastos(
    cliente_id: Annotated[str, Field(description="ID del cliente (cliente-001, cliente-002, cliente-003)")],
    ctx: Context,
) -> dict:
    """Resumen de gastos del mes actual agrupado por categoría. Requiere: gastos:read"""
    return await _run(
        ctx, "fintech_resumen_gastos", {"cliente_id": cliente_id}, "GET", f"/api/gastos/{cliente_id}/resumen"
    )


@mcp.tool(name="fintech_detalle_categorias")
async def fintech_detalle_categorias(
    cliente_id: Annotated[str, Field(description="ID del cliente (cliente-001, cliente-002, cliente-003)")],
    ctx: Context,
) -> dict:
    """Desglose de gastos comparando real vs presupuesto por categoría. Requiere: gastos:read"""
    return await _run(
        ctx,
        "fintech_detalle_categorias",
        {"cliente_id": cliente_id},
        "GET",
        f"/api/gastos/{cliente_id}/categorias",
    )


@mcp.tool(name="fintech_establecer_presupuesto")
async def fintech_establecer_presupuesto(
    cliente_id: Annotated[str, Field(description="ID del cliente")],
    categoria: Annotated[
        str, Field(description="Categoría: Alimentación|Transporte|Entretenimiento|Servicios|Salud|Educación")
    ],
    monto: Annotated[float, Field(gt=0, description="Monto del presupuesto mensual")],
    ctx: Context,
) -> dict:
    """Establece presupuesto mensual de una categoría. Solo admins. Requiere: gastos:write"""
    body = {"cliente_id": cliente_id, "categoria": categoria, "monto": monto}
    return await _run(
        ctx, "fintech_establecer_presupuesto", body, "POST", "/api/gastos/presupuesto", body=body
    )


@mcp.tool(name="fintech_ver_alertas")
async def fintech_ver_alertas(
    cliente_id: Annotated[str, Field(description="ID del cliente (cliente-001, cliente-002, cliente-003)")],
    ctx: Context,
) -> dict:
    """Categorías donde el gasto del mes supera el presupuesto. Requiere: gastos:read"""
    return await _run(
        ctx, "fintech_ver_alertas", {"cliente_id": cliente_id}, "GET", f"/api/gastos/{cliente_id}/alertas"
    )


# ── Server-side HTML rendering (variante de comparación) ─────────────────────
def _render_resumen_gastos_html(data: dict) -> str:
    """Renderiza el resumen de gastos como HTML completo con CSS inline.

    El objetivo educativo es comparar este render (server-side, determinista)
    contra el que produce Claude vía Artifacts React desde el JSON de
    `fintech_resumen_gastos`.
    """
    cliente_id = data.get("cliente_id", "?")
    mes = data.get("mes", "?")
    total = float(data.get("total_gastado", 0.0))
    cats = data.get("por_categoria", {}) or {}
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    if cats:
        max_g = max((v["gastado"] for v in cats.values()), default=1.0) or 1.0
        rows_list = []
        for cat, v in sorted(cats.items(), key=lambda kv: -kv[1]["gastado"]):
            pct = int((v["gastado"] / max_g) * 100)
            rows_list.append(
                f'<tr>'
                f'<td>{cat}</td>'
                f'<td style="text-align:right;font-variant-numeric:tabular-nums;">{v["gastado"]:,.2f}</td>'
                f'<td style="text-align:right;">{v["transacciones"]}</td>'
                f'<td><div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div></td>'
                f'</tr>'
            )
        rows_html = "".join(rows_list)
    else:
        rows_html = '<tr><td colspan="4" style="text-align:center;color:#94a3b8;">Sin datos</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Resumen · {cliente_id}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         padding: 2rem; background: #f8fafc; color: #0f172a; margin: 0; }}
  .container {{ max-width: 720px; margin: 0 auto; background: white; border-radius: 12px;
                padding: 2rem; box-shadow: 0 4px 12px rgba(15,23,42,0.08); }}
  .badge {{ display: inline-block; background: #dbeafe; color: #1e40af; padding: 0.25rem 0.6rem;
            border-radius: 4px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em;
            text-transform: uppercase; }}
  h1 {{ margin: 0.5rem 0 0.25rem; color: #1e293b; font-size: 1.75rem; }}
  .meta {{ color: #64748b; font-size: 0.875rem; }}
  .total {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white;
            padding: 1.5rem; border-radius: 8px; margin: 1.5rem 0; }}
  .total .label {{ opacity: 0.85; font-size: 0.7rem; text-transform: uppercase;
                   letter-spacing: 0.1em; }}
  .total .value {{ font-size: 2.5rem; font-weight: 700; margin-top: 0.25rem;
                   font-variant-numeric: tabular-nums; }}
  h2 {{ font-size: 0.75rem; color: #475569; text-transform: uppercase; letter-spacing: 0.1em;
        margin: 1.5rem 0 0.5rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th {{ background: #f1f5f9; text-align: left; padding: 0.75rem; color: #475569; font-weight: 600; }}
  td {{ padding: 0.75rem; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  .bar-track {{ height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; width: 120px; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, #6366f1, #8b5cf6); }}
  .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;
             color: #94a3b8; font-size: 0.75rem; line-height: 1.5; }}
  code {{ background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">
  <span class="badge">Server-rendered</span>
  <h1>Resumen de gastos</h1>
  <div class="meta">Cliente <strong>{cliente_id}</strong> · Mes {mes}</div>
  <div class="total">
    <div class="label">Total gastado</div>
    <div class="value">{total:,.2f} PEN</div>
  </div>
  <h2>Por categoría</h2>
  <table>
    <thead><tr><th>Categoría</th><th style="text-align:right;">Gastado</th>
      <th style="text-align:right;">Tx</th><th>Distribución</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="footer">
    Generado server-side por <code>mcp-fintech</code> · {timestamp}<br>
    Este HTML fue construido por Python con CSS inline (no por Claude).
    Compará con el prompt <code>alerta_presupuesto</code> o <code>resumen_cliente</code>
    que usan Artifacts React generados dinámicamente por el LLM.
  </div>
</div>
</body>
</html>"""


@mcp.tool(name="fintech_resumen_gastos_html")
async def fintech_resumen_gastos_html(
    cliente_id: Annotated[str, Field(description="ID del cliente (cliente-001, cliente-002, cliente-003)")],
    ctx: Context,
) -> dict:
    """Resumen de gastos PRE-RENDERIZADO en HTML por el server (no por Claude).

    Esta tool retorna HTML completo con estilos inline. Tu rol al exponerlo al usuario:

    1. Mostrá el HTML EXACTAMENTE como vino, en un artifact tipo `text/html`,
       SIN modificar markup ni regenerarlo como React/Recharts.
    2. Aclará al usuario que este render proviene del server-side (Python f-string + CSS),
       a diferencia de los prompts (`resumen_cliente`, `alerta_presupuesto`) que generan
       Artifacts React dinámicos. El propósito es comparar ambos enfoques.
    3. Devolvé también el JSON de los datos por si el usuario quiere ver la fuente cruda.

    Requiere: gastos:read
    """
    raw = await _run(
        ctx,
        "fintech_resumen_gastos_html",
        {"cliente_id": cliente_id},
        "GET",
        f"/api/gastos/{cliente_id}/resumen",
    )
    if "error" in raw:
        return raw
    return {
        "render_source": "server-side (Python f-string + CSS inline)",
        "render_format": "text/html",
        "instructions_for_assistant": (
            "Mostrá el campo `html` como artifact text/html SIN modificarlo. "
            "Recordale al usuario que este es render server-side, distinto del flujo "
            "del prompt `alerta_presupuesto` (que usa Artifact React generado por LLM)."
        ),
        "data": raw,
        "html": _render_resumen_gastos_html(raw),
    }


# ════════════════════════════════════════════════════════════════════════════
# TOOL — AUDITORÍA
# ════════════════════════════════════════════════════════════════════════════


@mcp.tool(name="fintech_ver_auditoria")
async def fintech_ver_auditoria(
    ctx: Context,
    limite: Annotated[int, Field(ge=1, le=100, description="Número de registros a retornar (1-100)")] = 20,
) -> dict:
    """
    Log de auditoría completo: quién usó qué tool, cuándo y con qué resultado.
    Solo admins. Requiere: cuentas:write (permiso exclusivo de admin)
    """
    key = _get_api_key(ctx)
    pool: asyncpg.Pool = ctx.request_context.lifespan_context["pool"]
    t0 = time.monotonic()
    auth = None
    try:
        auth = await _auth(pool, key, "fintech_ver_auditoria", {"limite": limite})
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT ac.nombre, ac.rol, al.tool_nombre,
                          al.status_code, al.latencia_ms, al.error_msg,
                          al.llamado_en::text AS llamado_en
                   FROM audit_log al
                   JOIN api_consumers ac ON al.consumer_id = ac.id
                   ORDER BY al.llamado_en DESC LIMIT $1""",
                limite,
            )
        ms = int((time.monotonic() - t0) * 1000)
        await _complete(pool, auth["audit_id"], 200, ms)
        return {"total": len(rows), "registros": [dict(r) for r in rows]}
    except PermissionError as e:
        code, msg = str(e).split("::", 1)
        return {"error": msg, "status": int(code)}
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        if auth:
            await _complete(pool, auth["audit_id"], 500, ms, str(e))
        return {"error": str(e), "status": 500}


# ── Server-side HTML rendering — variante de comparación (auditoría) ─────────
def _render_auditoria_html(rows: list[dict]) -> str:
    """HTML auto-contenido del audit log con coloreado por status_code."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total = len(rows)
    bloqueos = sum(1 for r in rows if (r.get("status_code") or 0) == 403)
    exitosas = [r for r in rows if (r.get("status_code") or 0) == 200]
    avg_latencia = sum((r.get("latencia_ms") or 0) for r in exitosas) / len(exitosas) if exitosas else 0

    if rows:
        rows_html = []
        for r in rows:
            status = r.get("status_code") or 0
            if status == 200:
                bg, color = "#ecfdf5", "#065f46"
            elif status == 403:
                bg, color = "#fef3c7", "#92400e"
            else:
                bg, color = "#fee2e2", "#991b1b"
            err = r.get("error_msg") or ""
            err_short = (err[:60] + "…") if len(err) > 60 else err
            rows_html.append(
                f'<tr style="background:{bg}">'
                f'<td style="color:#475569;font-variant-numeric:tabular-nums;">{r.get("llamado_en", "")[:19]}</td>'
                f'<td><strong>{r.get("nombre", "?")}</strong> <span style="color:#94a3b8">·</span> '
                f'<span style="font-size:0.7rem;text-transform:uppercase;color:#64748b;">{r.get("rol", "?")}</span></td>'
                f'<td><code>{r.get("tool_nombre", "?")}</code></td>'
                f'<td><span class="status-pill" style="background:{color}1f;color:{color}">{status}</span></td>'
                f'<td style="text-align:right;font-variant-numeric:tabular-nums;color:#475569;">'
                f'{(r.get("latencia_ms") or 0)} ms</td>'
                f'<td style="color:#64748b;font-size:0.75rem;">{err_short}</td>'
                f'</tr>'
            )
        body = "".join(rows_html)
    else:
        body = '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:2rem;">Sin registros</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Audit log · mcp-fintech</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         padding: 2rem; background: #f8fafc; color: #0f172a; margin: 0; }}
  .container {{ max-width: 1024px; margin: 0 auto; background: white; border-radius: 12px;
                padding: 2rem; box-shadow: 0 4px 12px rgba(15,23,42,0.08); }}
  .badge {{ display: inline-block; background: #dbeafe; color: #1e40af; padding: 0.25rem 0.6rem;
            border-radius: 4px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em;
            text-transform: uppercase; }}
  h1 {{ margin: 0.5rem 0 0.25rem; color: #1e293b; font-size: 1.75rem; }}
  .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 1.5rem; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
              gap: 0.75rem; margin: 1.5rem 0; }}
  .metric {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem;
             background: #f8fafc; }}
  .metric .label {{ font-size: 0.7rem; color: #64748b; text-transform: uppercase;
                    letter-spacing: 0.05em; }}
  .metric .value {{ font-size: 1.5rem; font-weight: 700; color: #0f172a;
                    margin-top: 0.25rem; font-variant-numeric: tabular-nums; }}
  .metric.warn .value {{ color: #b45309; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-top: 0.5rem; }}
  th {{ background: #f1f5f9; text-align: left; padding: 0.6rem 0.75rem; color: #475569;
        font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
        border-bottom: 1px solid #e2e8f0; }}
  td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid #e2e8f0; }}
  tr:last-child td {{ border-bottom: none; }}
  code {{ background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 3px;
          font-family: 'SF Mono', Menlo, monospace; font-size: 0.8rem; color: #475569; }}
  .status-pill {{ font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 999px;
                  font-size: 0.7rem; font-variant-numeric: tabular-nums; }}
  .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;
             color: #94a3b8; font-size: 0.75rem; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">
  <span class="badge">Server-rendered · admin</span>
  <h1>Audit log</h1>
  <div class="meta">{total} registros · render server-side · {timestamp}</div>

  <div class="metrics">
    <div class="metric"><div class="label">Total calls</div><div class="value">{total}</div></div>
    <div class="metric warn"><div class="label">Bloqueos 403</div><div class="value">{bloqueos}</div></div>
    <div class="metric"><div class="label">Latencia prom. (200)</div><div class="value">{avg_latencia:.0f} ms</div></div>
    <div class="metric"><div class="label">Tasa de bloqueo</div><div class="value">{(bloqueos / total * 100) if total else 0:.0f}%</div></div>
  </div>

  <table>
    <thead><tr><th>Timestamp UTC</th><th>Consumer</th><th>Tool</th>
      <th>Status</th><th style="text-align:right;">Latencia</th><th>Error</th></tr></thead>
    <tbody>{body}</tbody>
  </table>

  <div class="footer">
    Render server-side por <code>mcp-fintech</code>. Comparalo con el artifact React
    del prompt <code>auditoria_postmortem</code> para ver el mismo dato resuelto
    con dos tecnologías de presentación distintas.
  </div>
</div>
</body>
</html>"""


@mcp.tool(name="fintech_ver_auditoria_html")
async def fintech_ver_auditoria_html(
    ctx: Context,
    limite: Annotated[int, Field(ge=1, le=100, description="Número de registros a retornar (1-100)")] = 20,
) -> dict:
    """Audit log PRE-RENDERIZADO en HTML por el server (no por Claude).

    Solo admins. Mostrá el campo `html` como artifact tipo `text/html` SIN modificarlo.
    Aclará al usuario que es render server-side, complementario al post-mortem React
    del prompt `auditoria_postmortem`.

    Requiere: cuentas:write (admin)
    """
    key = _get_api_key(ctx)
    pool: asyncpg.Pool = ctx.request_context.lifespan_context["pool"]
    t0 = time.monotonic()
    auth = None
    try:
        auth = await _auth(pool, key, "fintech_ver_auditoria_html", {"limite": limite})
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT ac.nombre, ac.rol, al.tool_nombre,
                          al.status_code, al.latencia_ms, al.error_msg,
                          al.llamado_en::text AS llamado_en
                   FROM audit_log al
                   JOIN api_consumers ac ON al.consumer_id = ac.id
                   ORDER BY al.llamado_en DESC LIMIT $1""",
                limite,
            )
        ms = int((time.monotonic() - t0) * 1000)
        await _complete(pool, auth["audit_id"], 200, ms)
        rows_dicts = [dict(r) for r in rows]
        return {
            "render_source": "server-side (Python f-string + CSS inline)",
            "render_format": "text/html",
            "instructions_for_assistant": (
                "Mostrá el campo `html` como artifact text/html SIN modificarlo. "
                "Compará con el post-mortem React del prompt `auditoria_postmortem` "
                "para ver el contraste server-side vs LLM-generated."
            ),
            "total": len(rows_dicts),
            "registros": rows_dicts,
            "html": _render_auditoria_html(rows_dicts),
        }
    except PermissionError as e:
        code, msg = str(e).split("::", 1)
        return {"error": msg, "status": int(code)}
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        if auth:
            await _complete(pool, auth["audit_id"], 500, ms, str(e))
        return {"error": str(e), "status": 500}


if __name__ == "__main__":
    logger.info(
        "server.starting",
        server=MCP_SERVER_NAME,
        transport="streamable-http",
        port=mcp.settings.port,
        tools=16,
    )
    mcp.run(transport="streamable-http")
