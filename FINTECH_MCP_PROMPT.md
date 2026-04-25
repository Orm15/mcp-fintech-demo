# Fintech MCP Simulation — Prompt para Claude Code
# Stack: PostgreSQL + FastAPI + FastMCP | 3 contenedores | Auth por roles + Auditoría

---

## Contexto y objetivo

Construir una simulación completa de arquitectura MCP (Model Context Protocol) bancaria.
Claude Desktop consume tools financieras a través de un MCP server con autenticación por roles,
auditoría en PostgreSQL, y una API bancaria simulada con FastAPI.

**Arquitectura final — exactamente 3 contenedores:**
```
Claude Desktop  →  mcp-fintech  (:8000)  →  api-fintech  (:9000)
                        │
                   postgres     (:5432)   ← auth + auditoría + rate limiting
```

**Fuentes de decisiones técnicas aplicadas:**
- MCP skill oficial: transport streamable_http (SSE deprecado), Pydantic models, tool annotations, lifespan
- Docker best practices 2025: multi-stage builds, non-root user, exec form en CMD, healthchecks, .dockerignore
- FastAPI production: middleware global de auth, structured logging, exec form

---

## Instrucción de trabajo para Claude Code

Implementa el proyecto **en 3 fases ordenadas**. Al terminar cada fase ejecuta las validaciones
indicadas y NO avances si alguna falla. Reporta el output de cada validación antes de continuar.

---

# FASE 1 — PostgreSQL + estructura base

## Objetivo
Levantar PostgreSQL con schema completo y datos seed. Sin código de app todavía.

## Estructura de carpetas a crear

```
fintech-mcp/
├── docker-compose.yml        ← solo postgres por ahora
├── .env.example
├── .env                      ← cp de .env.example
├── .dockerignore
├── postgres/
│   └── init.sql
├── api-fintech/              ← vacía por ahora
└── mcp-fintech/              ← vacía por ahora
```

## .dockerignore (raíz del proyecto)

```
__pycache__/
*.pyc
*.pyo
.env
.env.*
!.env.example
*.log
.git/
.gitignore
.DS_Store
**/__pycache__/
```

## .env.example

```env
POSTGRES_PASSWORD=fintech123
FUNCTION_KEY=fintech-func-key-2024

# Keys de los consumidores (seed en init.sql)
# usuario normal → usr-maria-garcia-a3f9k2  (cuentas:read, gastos:read)
# admin          → adm-fintech-x9p2m7k1    (todo + auditoría)
```

## postgres/init.sql

```sql
CREATE TABLE IF NOT EXISTS api_consumers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          VARCHAR(100) NOT NULL,
    api_key         VARCHAR(100) NOT NULL UNIQUE,
    rol             VARCHAR(20)  NOT NULL CHECK (rol IN ('user', 'admin')),
    permisos        JSONB        NOT NULL DEFAULT '[]',
    rate_limit_hora INT          NOT NULL DEFAULT 100,
    activo          BOOLEAN      NOT NULL DEFAULT true,
    creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consumer_id     UUID        NOT NULL REFERENCES api_consumers(id),
    mcp_server      VARCHAR(50) NOT NULL,
    tool_nombre     VARCHAR(100) NOT NULL,
    parametros      JSONB,
    status_code     INT,
    error_msg       TEXT,
    latencia_ms     INT,
    llamado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_consumer ON audit_log(consumer_id);
CREATE INDEX idx_audit_tool     ON audit_log(tool_nombre);
CREATE INDEX idx_audit_fecha    ON audit_log(llamado_en DESC);

CREATE TABLE IF NOT EXISTS rate_limit_counter (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consumer_id     UUID        NOT NULL REFERENCES api_consumers(id),
    ventana_hora    VARCHAR(20) NOT NULL,
    total_llamadas  INT         NOT NULL DEFAULT 0,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (consumer_id, ventana_hora)
);

INSERT INTO api_consumers (nombre, api_key, rol, permisos, rate_limit_hora) VALUES
(
    'María García',
    'usr-maria-garcia-a3f9k2',
    'user',
    '["cuentas:read", "gastos:read"]',
    100
),
(
    'Admin Fintech',
    'adm-fintech-x9p2m7k1',
    'admin',
    '["cuentas:read","cuentas:write","transferencias:read","transferencias:write","gastos:read","gastos:write"]',
    1000
);
```

## docker-compose.yml (solo postgres en fase 1)

```yaml
version: "3.9"

networks:
  fintech-net:
    driver: bridge

volumes:
  postgres-data:

services:
  postgres:
    image: postgres:16-alpine
    container_name: fintech-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: fintechdb
      POSTGRES_USER: fintech
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    networks:
      - fintech-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fintech -d fintechdb"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
```

## Comandos a ejecutar

```bash
cp .env.example .env
docker compose up -d postgres
```

## ✅ VALIDACIONES FASE 1

```bash
# 1. Postgres healthy
docker compose ps postgres
# → Status debe ser "Up (healthy)"

# 2. Las 3 tablas existen
docker exec fintech-postgres psql -U fintech -d fintechdb -c "\dt"
# → api_consumers, audit_log, rate_limit_counter

# 3. Seed correcto
docker exec fintech-postgres psql -U fintech -d fintechdb \
  -c "SELECT nombre, rol, rate_limit_hora, permisos FROM api_consumers;"
# → 2 filas: María García (user, 100/h) y Admin Fintech (admin, 1000/h)
```

**Si algo falla, corregir antes de continuar a Fase 2.**

---

# FASE 2 — API Fintech (FastAPI)

## Objetivo
Un único contenedor FastAPI con todos los endpoints bancarios organizados en routers.
Simula una Azure Function App con múltiples módulos.

## Estructura

```
api-fintech/
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── main.py
├── routers/
│   ├── __init__.py
│   ├── cuentas.py
│   ├── transferencias.py
│   └── gastos.py
└── data/
    ├── __init__.py
    ├── cuentas.py
    ├── transferencias.py
    └── gastos.py
```

## api-fintech/.dockerignore

```
__pycache__/
*.pyc
.env
*.log
```

## api-fintech/Dockerfile

Best practices aplicadas: non-root user, exec form en CMD, copy requirements primero para cache.

```dockerfile
FROM python:3.12-slim

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
```

## api-fintech/requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.1
```

## api-fintech/data/cuentas.py

```python
CUENTAS = {
    "CTA-001": {"id":"CTA-001","cliente_id":"cliente-001","tipo":"ahorros",
                "moneda":"PEN","saldo":15420.50,"estado":"activa","fecha_apertura":"2021-03-15"},
    "CTA-002": {"id":"CTA-002","cliente_id":"cliente-001","tipo":"corriente",
                "moneda":"USD","saldo":3200.00,"estado":"activa","fecha_apertura":"2022-01-10"},
    "CTA-003": {"id":"CTA-003","cliente_id":"cliente-002","tipo":"ahorros",
                "moneda":"PEN","saldo":8750.00,"estado":"activa","fecha_apertura":"2020-07-22"},
    "CTA-004": {"id":"CTA-004","cliente_id":"cliente-003","tipo":"ahorros",
                "moneda":"PEN","saldo":22100.00,"estado":"activa","fecha_apertura":"2019-11-05"},
    "CTA-005": {"id":"CTA-005","cliente_id":"cliente-003","tipo":"corriente",
                "moneda":"PEN","saldo":5500.00,"estado":"activa","fecha_apertura":"2020-02-18"},
    "CTA-006": {"id":"CTA-006","cliente_id":"cliente-003","tipo":"empresarial",
                "moneda":"PEN","saldo":98000.00,"estado":"activa","fecha_apertura":"2023-05-01"},
}
CLIENTES = {
    "cliente-001": {"nombre":"María García","cuentas":["CTA-001","CTA-002"]},
    "cliente-002": {"nombre":"Carlos López","cuentas":["CTA-003"]},
    "cliente-003": {"nombre":"Ana Torres","cuentas":["CTA-004","CTA-005","CTA-006"]},
}
MOVIMIENTOS = {
    "CTA-001": [
        {"fecha":"2024-11-28","descripcion":"Depósito sueldo noviembre","monto":4500.00,"tipo":"credito"},
        {"fecha":"2024-11-25","descripcion":"Supermercado Wong","monto":-320.50,"tipo":"debito"},
        {"fecha":"2024-11-22","descripcion":"Netflix","monto":-45.90,"tipo":"debito"},
        {"fecha":"2024-11-20","descripcion":"Restaurante Astrid y Gastón","monto":-280.00,"tipo":"debito"},
        {"fecha":"2024-11-15","descripcion":"Transferencia recibida CTA-003","monto":500.00,"tipo":"credito"},
        {"fecha":"2024-11-10","descripcion":"Farmacia InkaFarma","monto":-89.00,"tipo":"debito"},
        {"fecha":"2024-11-05","descripcion":"Gasolina Primax","monto":-150.00,"tipo":"debito"},
    ],
    "CTA-002": [
        {"fecha":"2024-11-20","descripcion":"Amazon.com purchase","monto":-89.99,"tipo":"debito"},
        {"fecha":"2024-11-15","descripcion":"Transferencia internacional recibida","monto":500.00,"tipo":"credito"},
        {"fecha":"2024-11-10","descripcion":"Spotify Premium","monto":-9.99,"tipo":"debito"},
    ],
    "CTA-003": [
        {"fecha":"2024-11-28","descripcion":"Depósito sueldo noviembre","monto":3200.00,"tipo":"credito"},
        {"fecha":"2024-11-25","descripcion":"Supermercado Plaza Vea","monto":-210.00,"tipo":"debito"},
        {"fecha":"2024-11-20","descripcion":"Transferencia enviada CTA-001","monto":-500.00,"tipo":"debito"},
        {"fecha":"2024-11-15","descripcion":"Recibo agua Sedapal","monto":-85.00,"tipo":"debito"},
        {"fecha":"2024-11-10","descripcion":"Recibo luz Enel","monto":-120.00,"tipo":"debito"},
    ],
    "CTA-004": [
        {"fecha":"2024-11-28","descripcion":"Depósito sueldo noviembre","monto":8500.00,"tipo":"credito"},
        {"fecha":"2024-11-25","descripcion":"Supermercado Vivanda","monto":-450.00,"tipo":"debito"},
        {"fecha":"2024-11-22","descripcion":"Colegio mensualidad","monto":-1200.00,"tipo":"debito"},
        {"fecha":"2024-11-18","descripcion":"Combustible","monto":-200.00,"tipo":"debito"},
        {"fecha":"2024-11-10","descripcion":"Médico particular","monto":-350.00,"tipo":"debito"},
    ],
    "CTA-005": [
        {"fecha":"2024-11-26","descripcion":"Pago proveedor servicios","monto":-2000.00,"tipo":"debito"},
        {"fecha":"2024-11-20","descripcion":"Cobro honorarios","monto":3500.00,"tipo":"credito"},
    ],
    "CTA-006": [
        {"fecha":"2024-11-28","descripcion":"Ingreso ventas semana 4","monto":25000.00,"tipo":"credito"},
        {"fecha":"2024-11-21","descripcion":"Ingreso ventas semana 3","monto":18000.00,"tipo":"credito"},
        {"fecha":"2024-11-18","descripcion":"Pago planilla","monto":-15000.00,"tipo":"debito"},
        {"fecha":"2024-11-14","descripcion":"Ingreso ventas semana 2","monto":22000.00,"tipo":"credito"},
        {"fecha":"2024-11-10","descripcion":"Alquiler oficina","monto":-3500.00,"tipo":"debito"},
    ],
}
cuentas_store  = dict(CUENTAS)
clientes_store = {k: {"nombre": v["nombre"], "cuentas": list(v["cuentas"])} for k, v in CLIENTES.items()}
```

## api-fintech/data/transferencias.py

```python
TRANSFERENCIAS_INICIAL = {
    "TRF-001": {"id":"TRF-001","origen":"CTA-001","destino":"CTA-003","monto":500.00,
                "moneda":"PEN","descripcion":"Pago deuda","estado":"COMPLETADA","fecha":"2024-11-15 14:32:00"},
    "TRF-002": {"id":"TRF-002","origen":"CTA-004","destino":"CTA-001","monto":1000.00,
                "moneda":"PEN","descripcion":"Préstamo familiar","estado":"COMPLETADA","fecha":"2024-11-10 09:15:00"},
    "TRF-003": {"id":"TRF-003","origen":"CTA-006","destino":"CTA-005","monto":5000.00,
                "moneda":"PEN","descripcion":"Traslado operativo","estado":"PENDIENTE","fecha":"2024-11-28 16:00:00"},
    "TRF-004": {"id":"TRF-004","origen":"CTA-002","destino":"CTA-001","monto":200.00,
                "moneda":"USD","descripcion":"Conversión divisas","estado":"FALLIDA","fecha":"2024-11-20 11:22:00",
                "motivo_fallo":"Monedas incompatibles"},
}
LIMITES = {
    "cliente-001": {"limite_diario":5000.00,"usado_hoy":500.00,"moneda":"PEN"},
    "cliente-002": {"limite_diario":3000.00,"usado_hoy":0.00,"moneda":"PEN"},
    "cliente-003": {"limite_diario":50000.00,"usado_hoy":5000.00,"moneda":"PEN"},
}
transferencias_store = dict(TRANSFERENCIAS_INICIAL)
```

## api-fintech/data/gastos.py

```python
GASTOS = {
    "cliente-001": {"mes":"2024-11","categorias":{
        "Alimentación":    {"gastado":320.50,"transacciones":3},
        "Entretenimiento": {"gastado":325.90,"transacciones":2},
        "Transporte":      {"gastado":150.00,"transacciones":1},
        "Salud":           {"gastado":89.00, "transacciones":1},
    }},
    "cliente-002": {"mes":"2024-11","categorias":{
        "Alimentación":    {"gastado":210.00,"transacciones":2},
        "Servicios":       {"gastado":205.00,"transacciones":2},
        "Entretenimiento": {"gastado":0.00,  "transacciones":0},
    }},
    "cliente-003": {"mes":"2024-11","categorias":{
        "Alimentación": {"gastado":450.00, "transacciones":1},
        "Educación":    {"gastado":1200.00,"transacciones":1},
        "Transporte":   {"gastado":200.00, "transacciones":1},
        "Salud":        {"gastado":350.00, "transacciones":1},
    }},
}
PRESUPUESTOS_INICIAL = {
    "cliente-001": {"Alimentación":400.00,"Entretenimiento":200.00,"Transporte":300.00},
    "cliente-002": {"Alimentación":300.00,"Servicios":250.00},
    "cliente-003": {"Alimentación":500.00,"Educación":1000.00,"Salud":300.00},
}
presupuestos_store = {k: dict(v) for k, v in PRESUPUESTOS_INICIAL.items()}
```

## api-fintech/routers/cuentas.py

```python
import uuid
from fastapi import APIRouter, Header, HTTPException
from data.cuentas import cuentas_store, clientes_store, MOVIMIENTOS

router = APIRouter(prefix="/api/cuentas", tags=["cuentas"])

def _log(msg: str, caller: str) -> None:
    print(f"[cuentas] {msg} | caller={caller}", flush=True)

@router.get("/{cliente_id}")
def get_cuentas(cliente_id: str,
                x_caller_name: str = Header("system")):
    _log(f"GET cuentas/{cliente_id}", x_caller_name)
    if cliente_id not in clientes_store:
        raise HTTPException(404, f"Cliente '{cliente_id}' no existe")
    c = clientes_store[cliente_id]
    return {"cliente_id": cliente_id, "nombre": c["nombre"],
            "cuentas": [cuentas_store[cid] for cid in c["cuentas"] if cid in cuentas_store]}

@router.get("/{cuenta_id}/saldo")
def get_saldo(cuenta_id: str, x_caller_name: str = Header("system")):
    _log(f"GET saldo/{cuenta_id}", x_caller_name)
    if cuenta_id not in cuentas_store:
        raise HTTPException(404, "Cuenta no encontrada")
    c = cuentas_store[cuenta_id]
    return {"cuenta_id": cuenta_id, "saldo": c["saldo"],
            "moneda": c["moneda"], "tipo": c["tipo"]}

@router.get("/{cuenta_id}/movimientos")
def get_movimientos(cuenta_id: str, limit: int = 10,
                    x_caller_name: str = Header("system")):
    _log(f"GET movimientos/{cuenta_id}?limit={limit}", x_caller_name)
    if cuenta_id not in cuentas_store:
        raise HTTPException(404, "Cuenta no encontrada")
    movs = MOVIMIENTOS.get(cuenta_id, [])[:limit]
    return {"cuenta_id": cuenta_id, "movimientos": movs, "total": len(movs)}

@router.post("", status_code=201)
def crear_cuenta(body: dict, x_caller_name: str = Header("system")):
    _log("POST cuenta", x_caller_name)
    cliente_id = body.get("cliente_id")
    if not cliente_id or cliente_id not in clientes_store:
        raise HTTPException(404, "Cliente no encontrado")
    nueva_id = f"CTA-{str(uuid.uuid4())[:6].upper()}"
    nueva = {"id": nueva_id, "cliente_id": cliente_id,
             "tipo": body.get("tipo", "ahorros"),
             "moneda": body.get("moneda", "PEN"),
             "saldo": 0.0, "estado": "activa", "fecha_apertura": "2024-11-28"}
    cuentas_store[nueva_id] = nueva
    clientes_store[cliente_id]["cuentas"].append(nueva_id)
    return {"mensaje": "Cuenta creada", "cuenta": nueva}
```

## api-fintech/routers/transferencias.py

```python
import uuid
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException
from data.transferencias import transferencias_store, LIMITES

router = APIRouter(prefix="/api/transferencias", tags=["transferencias"])

def _log(msg: str, caller: str) -> None:
    print(f"[transferencias] {msg} | caller={caller}", flush=True)

@router.post("", status_code=201)
def crear_transferencia(body: dict, x_caller_name: str = Header("system")):
    _log("POST transferencia", x_caller_name)
    trf_id = f"TRF-{str(uuid.uuid4())[:6].upper()}"
    trf = {"id": trf_id, "origen": body.get("origen"), "destino": body.get("destino"),
           "monto": body.get("monto", 0), "moneda": "PEN",
           "descripcion": body.get("descripcion", ""),
           "estado": "COMPLETADA",
           "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    transferencias_store[trf_id] = trf
    return {"mensaje": "Transferencia ejecutada", "transferencia": trf}

@router.get("/historial/{cuenta_id}")
def get_historial(cuenta_id: str, x_caller_name: str = Header("system")):
    _log(f"GET historial/{cuenta_id}", x_caller_name)
    result = [t for t in transferencias_store.values()
              if t["origen"] == cuenta_id or t["destino"] == cuenta_id]
    return {"cuenta_id": cuenta_id, "transferencias": result, "total": len(result)}

@router.get("/limites/{cliente_id}")
def get_limites(cliente_id: str, x_caller_name: str = Header("system")):
    _log(f"GET limites/{cliente_id}", x_caller_name)
    if cliente_id not in LIMITES:
        raise HTTPException(404, "Cliente no encontrado")
    l = LIMITES[cliente_id]
    return {**l, "disponible_hoy": l["limite_diario"] - l["usado_hoy"], "cliente_id": cliente_id}

@router.get("/{transfer_id}")
def get_transferencia(transfer_id: str, x_caller_name: str = Header("system")):
    _log(f"GET transferencia/{transfer_id}", x_caller_name)
    if transfer_id not in transferencias_store:
        raise HTTPException(404, "Transferencia no encontrada")
    return transferencias_store[transfer_id]
```

## api-fintech/routers/gastos.py

```python
from fastapi import APIRouter, Header, HTTPException
from data.gastos import GASTOS, presupuestos_store

router = APIRouter(prefix="/api/gastos", tags=["gastos"])

def _log(msg: str, caller: str) -> None:
    print(f"[gastos] {msg} | caller={caller}", flush=True)

@router.get("/{cliente_id}/resumen")
def get_resumen(cliente_id: str, x_caller_name: str = Header("system")):
    _log(f"GET resumen/{cliente_id}", x_caller_name)
    if cliente_id not in GASTOS:
        raise HTTPException(404, "Cliente no encontrado")
    data = GASTOS[cliente_id]
    total = sum(v["gastado"] for v in data["categorias"].values())
    return {"cliente_id": cliente_id, "mes": data["mes"],
            "total_gastado": round(total, 2), "por_categoria": data["categorias"]}

@router.get("/{cliente_id}/categorias")
def get_categorias(cliente_id: str, x_caller_name: str = Header("system")):
    _log(f"GET categorias/{cliente_id}", x_caller_name)
    if cliente_id not in GASTOS:
        raise HTTPException(404, "Cliente no encontrado")
    cats = GASTOS[cliente_id]["categorias"]
    presups = presupuestos_store.get(cliente_id, {})
    return {"cliente_id": cliente_id, "categorias": {
        cat: {**datos, "presupuesto": presups.get(cat),
              "excedido": (datos["gastado"] > presups[cat]) if cat in presups else None}
        for cat, datos in cats.items()
    }}

@router.post("/presupuesto", status_code=201)
def set_presupuesto(body: dict, x_caller_name: str = Header("system")):
    _log("POST presupuesto", x_caller_name)
    cliente_id, categoria, monto = body.get("cliente_id"), body.get("categoria"), body.get("monto")
    if not all([cliente_id, categoria, monto is not None]):
        raise HTTPException(400, "Faltan: cliente_id, categoria, monto")
    presupuestos_store.setdefault(cliente_id, {})[categoria] = monto
    return {"mensaje": "Presupuesto actualizado", "cliente_id": cliente_id,
            "categoria": categoria, "monto": monto}

@router.get("/{cliente_id}/alertas")
def get_alertas(cliente_id: str, x_caller_name: str = Header("system")):
    _log(f"GET alertas/{cliente_id}", x_caller_name)
    if cliente_id not in GASTOS:
        raise HTTPException(404, "Cliente no encontrado")
    cats = GASTOS[cliente_id]["categorias"]
    presups = presupuestos_store.get(cliente_id, {})
    alertas = [
        {"categoria": cat, "gastado": d["gastado"], "presupuesto": presups[cat],
         "exceso": round(d["gastado"] - presups[cat], 2),
         "pct_excedido": round((d["gastado"] - presups[cat]) / presups[cat] * 100, 1)}
        for cat, d in cats.items()
        if cat in presups and d["gastado"] > presups[cat]
    ]
    return {"cliente_id": cliente_id, "total_alertas": len(alertas), "alertas": alertas}
```

## api-fintech/main.py

```python
import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from routers import cuentas, transferencias, gastos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("api-fintech")

FUNCTION_KEY = os.getenv("FUNCTION_KEY", "dev-key")

app = FastAPI(
    title="API Fintech",
    description="Simula Azure Function App — módulos: cuentas, transferencias, gastos",
    version="1.0.0",
)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in ("/health", "/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    key = request.headers.get("x-functions-key") or request.headers.get("X-Functions-Key")
    if key != FUNCTION_KEY:
        logger.warning(f"Unauthorized request to {request.url.path}")
        return JSONResponse(status_code=401, content={"detail": "Unauthorized: invalid function key"})
    return await call_next(request)

app.include_router(cuentas.router)
app.include_router(transferencias.router)
app.include_router(gastos.router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "api-fintech",
            "modulos": ["cuentas", "transferencias", "gastos"]}
```

## Agregar api-fintech al docker-compose.yml

```yaml
  api-fintech:
    build:
      context: ./api-fintech
      dockerfile: Dockerfile
    container_name: api-fintech
    restart: unless-stopped
    ports:
      - "9000:9000"
    environment:
      - FUNCTION_KEY=${FUNCTION_KEY}
    networks:
      - fintech-net
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

```bash
docker compose up --build -d api-fintech
```

## ✅ VALIDACIONES FASE 2

```bash
# 1. Contenedor healthy
docker compose ps api-fintech
# → Up (healthy)

# 2. Sin key → 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/api/cuentas/cliente-001
# → 401

# 3. Cuentas
curl -s http://localhost:9000/api/cuentas/cliente-001 \
  -H "X-Functions-Key: fintech-func-key-2024" | python3 -m json.tool
# → 2 cuentas (CTA-001, CTA-002)

# 4. Movimientos
curl -s "http://localhost:9000/api/cuentas/CTA-001/movimientos?limit=3" \
  -H "X-Functions-Key: fintech-func-key-2024" | python3 -m json.tool
# → 3 movimientos

# 5. Transferencia
curl -s -X POST http://localhost:9000/api/transferencias \
  -H "X-Functions-Key: fintech-func-key-2024" \
  -H "Content-Type: application/json" \
  -d '{"origen":"CTA-001","destino":"CTA-003","monto":200,"descripcion":"Test"}' \
  | python3 -m json.tool
# → transferencia COMPLETADA

# 6. Alertas cliente-003 (Educación y Salud excedidas)
curl -s http://localhost:9000/api/gastos/cliente-003/alertas \
  -H "X-Functions-Key: fintech-func-key-2024" | python3 -m json.tool
# → 2 alertas

# 7. Logs muestran módulo + caller
docker logs api-fintech --tail=10
# → líneas como "[cuentas] GET cuentas/cliente-001 | caller=system"
```

**Si algo falla, corregir antes de continuar a Fase 3.**

---

# FASE 3 — MCP Fintech (FastMCP con streamable_http)

## Objetivo
Un único MCP server con 13 tools usando FastMCP.
Aplica: streamable_http (no SSE), Pydantic models, tool annotations, lifespan para el pool de BD.

## Estructura

```
mcp-fintech/
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── server.py
```

## mcp-fintech/.dockerignore

```
__pycache__/
*.pyc
.env
*.log
```

## mcp-fintech/Dockerfile

Build context desde raíz para copiar auth.py compartido.

```dockerfile
FROM python:3.12-slim

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY mcp-fintech/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY mcp-fintech/server.py .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

CMD ["python", "server.py"]
```

## mcp-fintech/requirements.txt

```
mcp[cli]==1.3.0
httpx==0.27.0
asyncpg==0.29.0
pydantic==2.7.1
```

## mcp-fintech/server.py — implementación completa

Aplica: streamable_http, Pydantic BaseModel por tool, annotations, lifespan, helper DRY.

```python
import os
import json
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Any

import asyncpg
import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# ── Config ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mcp-fintech")

DATABASE_URL    = os.getenv("DATABASE_URL", "postgresql://fintech:fintech123@postgres:5432/fintechdb")
FUNCTION_BASE   = os.getenv("FUNCTION_BASE_URL", "http://api-fintech:9000")
FUNCTION_KEY    = os.getenv("FUNCTION_KEY", "dev-key")
MCP_SERVER_NAME = "fintech_mcp"

# ── Permisos por tool ────────────────────────────────────
TOOL_PERMISSIONS: dict[str, str] = {
    "fintech_consultar_cuentas":        "cuentas:read",
    "fintech_ver_saldo":                "cuentas:read",
    "fintech_ver_movimientos":          "cuentas:read",
    "fintech_crear_cuenta":             "cuentas:write",
    "fintech_realizar_transferencia":   "transferencias:write",
    "fintech_estado_transferencia":     "transferencias:read",
    "fintech_historial_transferencias": "transferencias:read",
    "fintech_consultar_limites":        "transferencias:read",
    "fintech_resumen_gastos":           "gastos:read",
    "fintech_detalle_categorias":       "gastos:read",
    "fintech_establecer_presupuesto":   "gastos:write",
    "fintech_ver_alertas":              "gastos:read",
    "fintech_ver_auditoria":            "cuentas:write",
}

# ── Lifespan — pool de BD ────────────────────────────────
@asynccontextmanager
async def app_lifespan(server):
    pool = None
    for attempt in range(1, 6):
        try:
            pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
            logger.info(f"Pool PostgreSQL creado (intento {attempt})")
            break
        except Exception as e:
            logger.warning(f"PostgreSQL no disponible, intento {attempt}/5: {e}")
            if attempt < 5:
                await asyncio.sleep(3)
    if pool is None:
        raise RuntimeError("No se pudo conectar a PostgreSQL")
    yield {"pool": pool}
    await pool.close()
    logger.info("Pool cerrado")

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
)

# ── Auth + auditoría ─────────────────────────────────────
def _get_api_key(ctx) -> str:
    try:
        h = ctx.request_context.request.headers
        return h.get("x-api-key") or h.get("X-API-Key") or ""
    except Exception:
        return os.getenv("TEST_API_KEY", "")

def _fn_headers(nombre: str, uid: str) -> dict:
    return {
        "X-Functions-Key": FUNCTION_KEY,
        "Content-Type": "application/json",
        "X-Caller-Name": nombre,
        "X-Caller-User-Id": uid,
    }

async def _auth(pool: asyncpg.Pool, api_key: str, tool: str, params: dict) -> dict:
    """Valida key, verifica permiso, registra audit_log, actualiza rate limit."""
    if not api_key:
        raise PermissionError("401::API key requerida. Configura X-API-Key en Claude Desktop.")

    async with pool.acquire() as conn:
        consumer = await conn.fetchrow(
            "SELECT id, nombre, rol, permisos, rate_limit_hora, activo "
            "FROM api_consumers WHERE api_key = $1", api_key
        )
        if not consumer:
            raise PermissionError("401::API key inválida")
        if not consumer["activo"]:
            raise PermissionError("403::Consumidor desactivado")

        ventana = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        counter = await conn.fetchrow(
            "SELECT total_llamadas FROM rate_limit_counter "
            "WHERE consumer_id = $1 AND ventana_hora = $2",
            consumer["id"], ventana
        )
        if (counter["total_llamadas"] if counter else 0) >= consumer["rate_limit_hora"]:
            raise PermissionError(f"429::Rate limit: {consumer['rate_limit_hora']}/hora alcanzado")

        permiso_req = TOOL_PERMISSIONS.get(tool)
        permisos = json.loads(consumer["permisos"])
        if permiso_req and permiso_req not in permisos:
            await conn.execute(
                "INSERT INTO audit_log (consumer_id, mcp_server, tool_nombre, parametros, "
                "status_code, error_msg, latencia_ms) VALUES ($1,$2,$3,$4,403,$5,0)",
                consumer["id"], MCP_SERVER_NAME, tool, json.dumps(params),
                f"Sin permiso: requiere {permiso_req}"
            )
            raise PermissionError(
                f"403::Sin permiso para '{tool}'. Requiere: {permiso_req}. "
                f"Rol '{consumer['rol']}' tiene: {permisos}"
            )

        audit_id = await conn.fetchval(
            "INSERT INTO audit_log (consumer_id, mcp_server, tool_nombre, parametros) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            consumer["id"], MCP_SERVER_NAME, tool, json.dumps(params)
        )
        await conn.execute(
            "INSERT INTO rate_limit_counter (consumer_id, ventana_hora, total_llamadas) VALUES ($1,$2,1) "
            "ON CONFLICT (consumer_id, ventana_hora) "
            "DO UPDATE SET total_llamadas = rate_limit_counter.total_llamadas + 1, actualizado_en = NOW()",
            consumer["id"], ventana
        )
        logger.info(f"{tool} | {consumer['nombre']} ({consumer['rol']})")
        return {"audit_id": str(audit_id),
                "consumer": {"id": str(consumer["id"]), "nombre": consumer["nombre"], "rol": consumer["rol"]}}

async def _complete(pool: asyncpg.Pool, audit_id: str, status: int, ms: int, err: str = None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE audit_log SET status_code=$1, latencia_ms=$2, error_msg=$3 WHERE id=$4",
            status, ms, err, audit_id
        )

async def _call(method: str, path: str, consumer: dict,
                query: dict = None, body: dict = None) -> Any:
    async with httpx.AsyncClient() as client:
        r = await client.request(
            method, f"{FUNCTION_BASE}{path}",
            params=query, json=body,
            headers=_fn_headers(consumer["nombre"], consumer["id"]),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

async def _run(ctx, tool: str, params: dict, method: str, path: str,
               query: dict = None, body: dict = None) -> dict:
    """Helper DRY: auth → HTTP → audit completo."""
    key = _get_api_key(ctx)
    pool: asyncpg.Pool = ctx.request_context.lifespan_state["pool"]
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


# ════════════════════════════════════════════════════════
# TOOLS — CUENTAS
# ════════════════════════════════════════════════════════

class ConsultarCuentasInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cliente_id: str = Field(..., description="ID del cliente (cliente-001, cliente-002, cliente-003)")

class VerSaldoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cuenta_id: str = Field(..., description="ID de la cuenta (CTA-001 al CTA-006)")

class VerMovimientosInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cuenta_id: str = Field(..., description="ID de la cuenta")
    limit: int = Field(default=10, ge=1, le=50, description="Número de movimientos a retornar (1-50)")

class CrearCuentaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cliente_id: str = Field(..., description="ID del cliente")
    tipo: str = Field(..., description="Tipo de cuenta: ahorros | corriente | empresarial")
    moneda: str = Field(default="PEN", description="Moneda: PEN | USD")


@mcp.tool(name="fintech_consultar_cuentas",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_consultar_cuentas(params: ConsultarCuentasInput, ctx=None) -> dict:
    """Consulta todas las cuentas bancarias de un cliente con saldos actuales. Requiere: cuentas:read"""
    return await _run(ctx, "fintech_consultar_cuentas", params.model_dump(),
                      "GET", f"/api/cuentas/{params.cliente_id}")

@mcp.tool(name="fintech_ver_saldo",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_ver_saldo(params: VerSaldoInput, ctx=None) -> dict:
    """Obtiene el saldo actual de una cuenta específica. Requiere: cuentas:read"""
    return await _run(ctx, "fintech_ver_saldo", params.model_dump(),
                      "GET", f"/api/cuentas/{params.cuenta_id}/saldo")

@mcp.tool(name="fintech_ver_movimientos",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_ver_movimientos(params: VerMovimientosInput, ctx=None) -> dict:
    """Retorna los últimos movimientos de una cuenta bancaria. Requiere: cuentas:read"""
    return await _run(ctx, "fintech_ver_movimientos", params.model_dump(),
                      "GET", f"/api/cuentas/{params.cuenta_id}/movimientos",
                      query={"limit": params.limit})

@mcp.tool(name="fintech_crear_cuenta",
          annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False})
async def fintech_crear_cuenta(params: CrearCuentaInput, ctx=None) -> dict:
    """Crea una nueva cuenta bancaria para un cliente. Solo admins. Requiere: cuentas:write"""
    return await _run(ctx, "fintech_crear_cuenta", params.model_dump(),
                      "POST", "/api/cuentas", body=params.model_dump())


# ════════════════════════════════════════════════════════
# TOOLS — TRANSFERENCIAS
# ════════════════════════════════════════════════════════

class RealizarTransferenciaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    origen: str = Field(..., description="ID cuenta origen (ej: CTA-001)")
    destino: str = Field(..., description="ID cuenta destino (ej: CTA-003)")
    monto: float = Field(..., gt=0, description="Monto a transferir (mayor que 0)")
    descripcion: str = Field(default="", description="Descripción opcional de la transferencia")

class EstadoTransferenciaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    transfer_id: str = Field(..., description="ID de la transferencia (ej: TRF-001)")

class HistorialTransferenciasInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cuenta_id: str = Field(..., description="ID de la cuenta (enviadas y recibidas)")

class ConsultarLimitesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cliente_id: str = Field(..., description="ID del cliente")


@mcp.tool(name="fintech_realizar_transferencia",
          annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False})
async def fintech_realizar_transferencia(params: RealizarTransferenciaInput, ctx=None) -> dict:
    """Ejecuta una transferencia bancaria entre dos cuentas. Solo admins. Requiere: transferencias:write"""
    return await _run(ctx, "fintech_realizar_transferencia", params.model_dump(),
                      "POST", "/api/transferencias", body=params.model_dump())

@mcp.tool(name="fintech_estado_transferencia",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_estado_transferencia(params: EstadoTransferenciaInput, ctx=None) -> dict:
    """Estado de una transferencia: COMPLETADA | PENDIENTE | FALLIDA. Requiere: transferencias:read"""
    return await _run(ctx, "fintech_estado_transferencia", params.model_dump(),
                      "GET", f"/api/transferencias/{params.transfer_id}")

@mcp.tool(name="fintech_historial_transferencias",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_historial_transferencias(params: HistorialTransferenciasInput, ctx=None) -> dict:
    """Historial de transferencias de una cuenta (enviadas y recibidas). Requiere: transferencias:read"""
    return await _run(ctx, "fintech_historial_transferencias", params.model_dump(),
                      "GET", f"/api/transferencias/historial/{params.cuenta_id}")

@mcp.tool(name="fintech_consultar_limites",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_consultar_limites(params: ConsultarLimitesInput, ctx=None) -> dict:
    """Límites diarios de transferencia y monto usado hoy. Requiere: transferencias:read"""
    return await _run(ctx, "fintech_consultar_limites", params.model_dump(),
                      "GET", f"/api/transferencias/limites/{params.cliente_id}")


# ════════════════════════════════════════════════════════
# TOOLS — GASTOS
# ════════════════════════════════════════════════════════

class ClienteIdInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cliente_id: str = Field(..., description="ID del cliente (cliente-001, cliente-002, cliente-003)")

class EstablecerPresupuestoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    cliente_id: str = Field(..., description="ID del cliente")
    categoria: str = Field(..., description="Categoría: Alimentación|Transporte|Entretenimiento|Servicios|Salud|Educación")
    monto: float = Field(..., gt=0, description="Monto del presupuesto mensual")


@mcp.tool(name="fintech_resumen_gastos",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_resumen_gastos(params: ClienteIdInput, ctx=None) -> dict:
    """Resumen de gastos del mes actual agrupado por categoría. Requiere: gastos:read"""
    return await _run(ctx, "fintech_resumen_gastos", params.model_dump(),
                      "GET", f"/api/gastos/{params.cliente_id}/resumen")

@mcp.tool(name="fintech_detalle_categorias",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_detalle_categorias(params: ClienteIdInput, ctx=None) -> dict:
    """Desglose de gastos comparando real vs presupuesto por categoría. Requiere: gastos:read"""
    return await _run(ctx, "fintech_detalle_categorias", params.model_dump(),
                      "GET", f"/api/gastos/{params.cliente_id}/categorias")

@mcp.tool(name="fintech_establecer_presupuesto",
          annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True})
async def fintech_establecer_presupuesto(params: EstablecerPresupuestoInput, ctx=None) -> dict:
    """Establece presupuesto mensual de una categoría. Solo admins. Requiere: gastos:write"""
    return await _run(ctx, "fintech_establecer_presupuesto", params.model_dump(),
                      "POST", "/api/gastos/presupuesto", body=params.model_dump())

@mcp.tool(name="fintech_ver_alertas",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_ver_alertas(params: ClienteIdInput, ctx=None) -> dict:
    """Categorías donde el gasto del mes supera el presupuesto. Requiere: gastos:read"""
    return await _run(ctx, "fintech_ver_alertas", params.model_dump(),
                      "GET", f"/api/gastos/{params.cliente_id}/alertas")


# ════════════════════════════════════════════════════════
# TOOL — AUDITORÍA
# ════════════════════════════════════════════════════════

class VerAuditoriaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limite: int = Field(default=20, ge=1, le=100, description="Número de registros a retornar (1-100)")


@mcp.tool(name="fintech_ver_auditoria",
          annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
async def fintech_ver_auditoria(params: VerAuditoriaInput, ctx=None) -> dict:
    """
    Log de auditoría completo: quién usó qué tool, cuándo y con qué resultado.
    Solo admins. Requiere: cuentas:write (permiso exclusivo de admin)
    """
    key = _get_api_key(ctx)
    pool: asyncpg.Pool = ctx.request_context.lifespan_state["pool"]
    t0 = time.monotonic()
    auth = None
    try:
        auth = await _auth(pool, key, "fintech_ver_auditoria", params.model_dump())
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT ac.nombre, ac.rol, al.tool_nombre,
                          al.status_code, al.latencia_ms, al.error_msg,
                          al.llamado_en::text AS llamado_en
                   FROM audit_log al
                   JOIN api_consumers ac ON al.consumer_id = ac.id
                   ORDER BY al.llamado_en DESC LIMIT $1""",
                params.limite
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Iniciando {MCP_SERVER_NAME} con streamable_http en :{port} — 13 tools")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
```

## Agregar mcp-fintech al docker-compose.yml

```yaml
  mcp-fintech:
    build:
      context: .
      dockerfile: mcp-fintech/Dockerfile
    container_name: mcp-fintech
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - FUNCTION_BASE_URL=http://api-fintech:9000
      - FUNCTION_KEY=${FUNCTION_KEY}
      - DATABASE_URL=postgresql://fintech:${POSTGRES_PASSWORD}@postgres:5432/fintechdb
      - PORT=8000
    networks:
      - fintech-net
    depends_on:
      postgres:
        condition: service_healthy
      api-fintech:
        condition: service_healthy
```

```bash
docker compose up --build -d mcp-fintech
```

## ✅ VALIDACIONES FASE 3

```bash
# 1. Exactamente 3 contenedores Up
docker compose ps
# → postgres (healthy) + api-fintech (healthy) + mcp-fintech (Up)

# 2. Log de arranque correcto
docker logs mcp-fintech --tail=5
# → "Pool PostgreSQL creado"
# → "Iniciando fintech_mcp con streamable_http en :8000 — 13 tools"

# 3. MCP Inspector (streamable-http, no SSE)
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
# Abrir http://localhost:5173
# Agregar header: X-API-Key: usr-maria-garcia-a3f9k2
# → 13 tools listadas con prefijo fintech_

# 4. Tool de lectura con usuario normal → OK
# Ejecutar: fintech_consultar_cuentas con cliente_id=cliente-001
# → JSON con CTA-001 y CTA-002

# 5. Tool de escritura con usuario normal → 403
# Ejecutar: fintech_realizar_transferencia con cualquier valor
# → {"error": "Sin permiso para 'fintech_realizar_transferencia'...", "status": 403}

# 6. Verificar 403 en auditoría
docker exec fintech-postgres psql -U fintech -d fintechdb -c "
SELECT ac.nombre, al.tool_nombre, al.status_code, al.error_msg
FROM audit_log al JOIN api_consumers ac ON al.consumer_id = ac.id
WHERE al.status_code = 403;"
# → María García | fintech_realizar_transferencia | 403 | Sin permiso...

# 7. Tool con admin → OK
# Cambiar header a X-API-Key: adm-fintech-x9p2m7k1
# Ejecutar: fintech_realizar_transferencia
#   origen=CTA-001, destino=CTA-003, monto=500, descripcion="Test admin"
# → transferencia COMPLETADA

# 8. Auditoría desde Claude
# Ejecutar: fintech_ver_auditoria con limite=10
# → todos los llamados anteriores incluyendo el 403 de María

# 9. Rate limit counter funcionando
docker exec fintech-postgres psql -U fintech -d fintechdb -c "
SELECT ac.nombre, rl.total_llamadas, ac.rate_limit_hora
FROM rate_limit_counter rl JOIN api_consumers ac ON rl.consumer_id = ac.id;"
# → contadores incrementados
```

---

# FASE 4 — README + Claude Desktop

## README.md en la raíz

```markdown
# Fintech MCP Simulation

Simulación de arquitectura MCP bancaria con autenticación por roles y auditoría en PostgreSQL.

## Stack (3 contenedores)

| Contenedor   | Puerto | Rol |
|-------------|--------|-----|
| postgres    | 5432   | Auth, auditoría, rate limiting |
| api-fintech | 9000   | Endpoints bancarios (FastAPI) |
| mcp-fintech | 8000   | 13 MCP tools (FastMCP streamable-http) |

## Setup

\`\`\`bash
cp .env.example .env
docker compose up --build
\`\`\`

## Usuarios

| Key | Rol | Permisos |
|-----|-----|---------|
| usr-maria-garcia-a3f9k2 | user  | cuentas:read, gastos:read |
| adm-fintech-x9p2m7k1   | admin | todo + auditoría |

## Datos de prueba

- Clientes: cliente-001, cliente-002, cliente-003
- Cuentas: CTA-001 al CTA-006
- Transferencias: TRF-001 al TRF-004

## Claude Desktop

macOS: ~/Library/Application Support/Claude/claude_desktop_config.json

\`\`\`json
{
  "mcpServers": {
    "fintech": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp",
               "--header", "X-API-Key:usr-maria-garcia-a3f9k2"]
    }
  }
}
\`\`\`

Para admin: cambiar key a adm-fintech-x9p2m7k1. Reiniciar Claude Desktop después.

## Prompts de prueba

Como usuario normal:
- "¿Cuáles son las cuentas del cliente-001?"
- "Muéstrame los últimos 5 movimientos de CTA-004"
- "¿El cliente-003 tiene alertas de presupuesto?" 
- "Realiza una transferencia de 100 soles" → debe dar error 403

Como admin:
- "Dame un resumen financiero completo del cliente-001"
- "Realiza una transferencia de 500 soles de CTA-001 a CTA-003"
- "Muéstrame la auditoría del sistema"

## Auditoría en PostgreSQL

\`\`\`bash
docker exec fintech-postgres psql -U fintech -d fintechdb -c "
SELECT ac.nombre, al.tool_nombre, al.status_code, al.latencia_ms, al.llamado_en::text
FROM audit_log al JOIN api_consumers ac ON al.consumer_id = ac.id
ORDER BY al.llamado_en DESC LIMIT 20;"
\`\`\`

## Comandos

\`\`\`bash
docker compose ps                    # estado
docker compose logs -f mcp-fintech   # logs MCP
docker compose logs -f api-fintech   # logs API
docker compose restart mcp-fintech   # reiniciar MCP
docker compose down -v               # reset completo
\`\`\`
```

## ✅ VALIDACIONES FASE 4 — prueba end-to-end

```bash
# 1. Instalar mcp-remote si no está
npx mcp-remote --version

# 2. Configurar Claude Desktop con key de usuario normal y reiniciar
# → "fintech" debe aparecer en el panel de tools

# 3. Prompt básico como usuario normal
# "¿Cuáles son las cuentas del cliente-001?"
# → Claude llama a fintech_consultar_cuentas y muestra CTA-001 y CTA-002

# 4. Verificar en auditoría
docker exec fintech-postgres psql -U fintech -d fintechdb -c "
SELECT ac.nombre, al.tool_nombre, al.status_code, al.latencia_ms
FROM audit_log al JOIN api_consumers ac ON al.consumer_id = ac.id
ORDER BY al.llamado_en DESC LIMIT 3;"
# → María García | fintech_consultar_cuentas | 200 | Xms

# 5. Probar bloqueo de permisos
# "Realiza una transferencia de 100 soles de CTA-001 a CTA-003"
# → Claude reporta el 403 con mensaje descriptivo

# 6. Cambiar key a admin y reiniciar Claude Desktop
# "Dame un resumen financiero completo del cliente-001"
# → Claude llama a fintech_consultar_cuentas + fintech_historial_transferencias
#   + fintech_ver_alertas y consolida la respuesta

# 7. Auditoría con admin
# "Muéstrame la auditoría del sistema, últimos 10 registros"
# → Claude llama a fintech_ver_auditoria y muestra incluyendo el 403 anterior
```

---

# Checklist final

- [ ] `docker compose up --build` levanta exactamente 3 contenedores sin errores
- [ ] `docker compose ps` muestra los 3 en estado healthy/Up
- [ ] MCP Inspector lista 13 tools con prefijo `fintech_` en `http://localhost:8000/mcp`
- [ ] Usuario normal puede leer, recibe 403 descriptivo al intentar escribir
- [ ] Admin puede ejecutar transferencias y ver auditoría real de PostgreSQL
- [ ] Cada llamada (exitosa o fallida) aparece en `audit_log` con latencia y resultado
- [ ] El prompt de resumen financiero activa múltiples tools en una sola conversación

---

# Notas técnicas aplicadas

## MCP (skill oficial)
- Transport: `streamable-http` — SSE está deprecado
- Tool naming: prefijo `fintech_` en todas las tools para evitar conflictos en multi-MCP
- Pydantic BaseModel con Field() en cada tool — no parámetros sueltos
- Tool annotations: readOnlyHint, destructiveHint, idempotentHint en todas
- Lifespan: el pool de asyncpg se crea al inicio y se comparte vía `lifespan_state`
- Helper `_run()` DRY: elimina duplicación del flujo auth→HTTP→audit en todas las tools

## Docker (best practices 2025)
- Non-root user en ambos Dockerfiles (appuser:appgroup)
- Exec form en CMD — garantiza graceful shutdown y lifespan events de FastAPI
- Copy requirements antes del código — aprovecha cache de capas Docker
- .dockerignore por servicio — evita copiar __pycache__, .env, logs
- `restart: unless-stopped` en todos los servicios de app
- `read-only` mount en postgres/init.sql (`:ro`)
- healthcheck en api-fintech para que mcp-fintech solo arranque cuando la API está lista