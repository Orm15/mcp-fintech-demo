# ADR-0002: Transporte streamable-http (no SSE) para el MCP server

- **Estado:** Aceptado
- **Fecha:** 2026-04-25

## Contexto

El servidor MCP necesita ser accesible desde Claude Desktop a través de `mcp-remote`. El MCP SDK de Python (`mcp[cli]`) soporta tres transportes:

1. **stdio** — proceso local hablando por stdin/stdout. Solo sirve si Claude Desktop spawneara el proceso.
2. **sse** — Server-Sent Events sobre HTTP. Marcado como **deprecated** en la spec MCP a favor de streamable-http.
3. **streamable-http** — sucesor de SSE. Bidireccional via HTTP POST con sesiones persistentes.

El requisito del proyecto es que el MCP corra como un servicio en Docker accesible por red, lo que descarta stdio.

## Decisión

Usar **`transport="streamable-http"`** en `FastMCP.run()`.

```python
mcp = FastMCP(
    "fintech_mcp",
    lifespan=app_lifespan,
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)
# ...
mcp.run(transport="streamable-http")
```

Configuración relevante:
- Endpoint: `POST /mcp/` (la trailing-slash es importante — sin ella el SDK responde con 307 redirect).
- Las requests deben llevar `Accept: application/json, text/event-stream`.
- La sesión se crea en el `initialize` y devuelve el header `MCP-Session-Id`.
- Llamadas posteriores deben incluir `MCP-Session-Id`.

## Consecuencias

**Positivas:**
- Transporte alineado con la spec actual de MCP — sigue funcionando con clientes nuevos.
- Bidireccional sin las limitaciones de SSE (un solo canal del server al client).
- `mcp-remote` (proxy oficial) lo soporta nativamente para conectar Claude Desktop a servidores remotos.

**Negativas:**
- Requiere `mcp[cli]>=1.6.0`. La versión 1.3.0 inicial no lo soporta — tuvimos que upgradar a 1.9.4 durante la implementación (ver CHANGELOG).
- El protocolo de sesión añade complejidad vs un POST simple — no se puede llamar tools sin pasar por el handshake `initialize` + `notifications/initialized`.

**Neutras:**
- `host` y `port` se pasan en el constructor de `FastMCP`, no en `run()` (el `run()` de mcp 1.9.4 solo acepta `transport` y `mount_path`).

## Alternativas consideradas

- **stdio** — descartado: requiere que Claude Desktop spawnee el proceso, incompatible con un servicio Dockerizado.
- **sse** — descartado: deprecado en la spec MCP, futuro incierto.
- **Servidor HTTP custom (no FastMCP)** — implica reimplementar el protocolo MCP. No tiene valor en este demo.

## Referencias

- [MCP Spec — Transports](https://modelcontextprotocol.io/specification/server/transports)
- [`mcp-remote` proxy](https://www.npmjs.com/package/mcp-remote)
