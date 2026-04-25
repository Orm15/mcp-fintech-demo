# ADR-0004: Lifespan + retry para el pool de PostgreSQL

- **Estado:** Aceptado
- **Fecha:** 2026-04-25

## Contexto

`mcp-fintech` y `api-fintech` arrancan en paralelo con `postgres` en docker-compose. Aunque `depends_on: condition: service_healthy` espera al healthcheck de Postgres, hay una ventana de carrera entre:
- Postgres reportando `pg_isready` → ok
- El pool de la app abriendo conexiones → puede fallar transitoriamente con `connection refused` o `the database system is starting up`

El primer arranque sin retry hacía que el contenedor entrara en crash-loop hasta que Docker desistía.

## Decisión

Implementar **retry con backoff** dentro del lifespan de cada servicio:

**`mcp-fintech/server.py`** (asyncpg):
```python
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
```

**`api-fintech/infrastructure/database.py`** (psycopg2):
```python
def init_pool(retries: int = 5, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL)
            return
        except OperationalError:
            if attempt < retries:
                time.sleep(delay)
            else:
                raise
```

Wired vía `@asynccontextmanager` (FastAPI lifespan / FastMCP lifespan).

## Consecuencias

**Positivas:**
- Arranque robusto: tolera 5 × 3s = 15 segundos de Postgres aún inicializándose.
- Logs claros: `Pool PostgreSQL creado (intento N)` documenta cuántos retries fueron necesarios — útil para detectar regresiones de timing.
- Lifespan también limpia el pool en shutdown.

**Negativas:**
- Si Postgres está realmente caído, el contenedor tarda 15s en fallar. Aceptable.
- Hardcoded en 5 intentos / 3s delay. En producción serían env vars.

**Neutras:**
- El healthcheck de Postgres (`pg_isready`) sigue siendo necesario para `depends_on` — el retry es defensa en profundidad.

## Alternativas consideradas

- **Confiar solo en healthchecks** — vulnerable a ventanas de carrera. Reportes empíricos lo confirmaron.
- **`wait-for-it.sh` o `dockerize`** — mueve el problema al entrypoint, agrega una dependencia extra. El retry en el lifespan es más Pythonic y permite logs estructurados.
- **Retry decorator (`tenacity`)** — válido pero overkill para un loop de 5 iteraciones; `tenacity` brilla con backoff exponencial + jitter, no es necesario aquí.

## Referencias

- [docker-compose — `depends_on` condition: service_healthy](https://docs.docker.com/reference/compose-file/services/#depends_on)
