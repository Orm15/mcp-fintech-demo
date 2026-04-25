# Changelog

Todos los cambios notables de este proyecto.

Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Removed
- **6 MCP prompts** (`@mcp.prompt`) — gatillaban un bug de pipelining en `mcp-remote 0.1.38` y la versión actual de Claude Desktop no los surface en la UI. Sus textos quedaron inline en `docs/pruebas/` para que se peguen como prompts directos. Ver [#30](https://github.com/Orm15/mcp-fintech-demo/issues/30).

### Added
- 3 tools HTML server-rendered para contraste server-side vs LLM Artifacts:
  - `fintech_resumen_gastos_html` (resumen de gastos como tabla con barra de distribución).
  - `fintech_consultar_cuentas_html` (cuentas como tarjetas estilo "bank card").
  - `fintech_ver_auditoria_html` (audit log con coloreado por status code, admin only).
- `docs/pruebas/` — bitácora de tests manuales en Claude Desktop con plantilla de evidencia visual + folder de capturas de pantalla.
- Suite de tests pytest: 32 unit (use cases + auth/permissions) + integration (testcontainers postgres) + 15 security (auth, permissions, audit, input validation).
- GitHub Actions CI: lint, unit, integration, security scans (bandit, pip-audit, gitleaks, trivy), e2e contra el compose stack.
- Pre-commit hooks: ruff, gitleaks, bandit, common file checks.
- Dependabot semanal para pip/Docker/GitHub Actions.
- Makefile con targets `up`, `down`, `test-*`, `lint`, `audit`, `psql`, `audit-log`.
- ADRs en `docs/adr/`: Clean+Hex, streamable-http, Protocol vs ABC ports, lifespan retry.
- Diagramas Mermaid en README (flujo end-to-end + arquitectura de capas).
- Logging estructurado JSON con `structlog` en ambos servicios.
- Healthcheck `/health` en `mcp-fintech` con pool lazy initialization.
- Devcontainer (`.devcontainer/devcontainer.json`) para VS Code.

### Changed
- `mcp-fintech` upgrade `mcp[cli]` 1.3.0 → 1.9.4 para soportar transporte `streamable-http`.
- Refactor de tools MCP: parámetros individuales con `Annotated[T, Field(...)]` + `ctx: Context` (la versión 1.9.4 no soporta wrappers Pydantic en la signature del tool).
- `host`/`port` se pasan en el constructor `FastMCP(...)` en vez de `run()`.
- `ctx.request_context.lifespan_state` → `lifespan_context` (rename en mcp 1.9.4).
- URL-encode del nombre del consumer en headers HTTP entre mcp-fintech y api-fintech (caracteres no-ASCII).
- Pool de PostgreSQL en `mcp-fintech` ahora es singleton compartido entre sesiones MCP y `/health` (antes se creaba por sesión).

## [0.1.0] — 2026-04-25

### Added
- Stack de 3 contenedores: PostgreSQL 16, api-fintech (FastAPI), mcp-fintech (FastMCP).
- 13 tools MCP con prefijo `fintech_` cubriendo cuentas, transferencias, gastos y auditoría.
- Auth por roles (user/admin) con permisos granulares (`cuentas:read`, `transferencias:write`, etc.).
- Rate limiting por consumer (100/hora) con ventana horaria.
- Audit log persistente: cada llamada queda registrada con consumer, tool, params, status, latencia, error.
- 2 API keys de prueba: `usr-maria-garcia-a3f9k2` (user), `adm-fintech-x9p2m7k1` (admin).
- Arquitectura Clean + Hexagonal en `api-fintech` (`domain/` → `application/` → `adapters/` → `infrastructure/`).
- Lifespan + retry (5 × 3s) para el pool de PostgreSQL.
- Healthcheck `pg_isready` en Postgres + endpoint `/health` en api-fintech.
- README con setup, prompts de prueba, comandos útiles y configuración para Claude Desktop vía `mcp-remote`.
