import logging
import os
from contextlib import asynccontextmanager

import structlog
from adapters.primary.http import cuentas, gastos, transferencias
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from infrastructure.database import init_pool

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
logger = structlog.get_logger("api-fintech")

FUNCTION_KEY = os.getenv("FUNCTION_KEY", "dev-key")
_PUBLIC_PATHS = {"/health", "/", "/docs", "/openapi.json", "/redoc"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield


app = FastAPI(
    title="API Fintech",
    description="Simula Azure Function App — módulos: cuentas, transferencias, gastos",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    key = request.headers.get("x-functions-key") or request.headers.get("X-Functions-Key")
    if key != FUNCTION_KEY:
        logger.warning(
            "auth.unauthorized", path=request.url.path, caller=request.headers.get("X-Caller-Name", "?")
        )
        return JSONResponse(status_code=401, content={"detail": "Unauthorized: invalid function key"})
    return await call_next(request)


app.include_router(cuentas.router)
app.include_router(transferencias.router)
app.include_router(gastos.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "api-fintech", "modulos": ["cuentas", "transferencias", "gastos"]}
