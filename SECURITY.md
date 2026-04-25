# Security

Este es un proyecto **demo**. NO está endurecido para producción. Esta nota documenta el modelo de amenazas asumido y dónde están las brechas conscientes vs los siguientes pasos.

## Modelo de amenazas (demo)

**Lo que el demo SÍ defiende:**
- Llamadas a tools MCP sin API key válida → 401.
- Usuario sin permiso intentando una tool restringida → 403 + registro en `audit_log`.
- Rate limit por consumer (100 calls/hora) → 429.
- Inyección SQL en parámetros: queries parametrizadas en todos los repos.
- Auditoría inmutable por llamada: consumer, tool, params, status, latencia, error.

**Lo que el demo NO defiende (consciente):**
- API keys en plaintext en BD (deberían ser hashes argon2).
- Sin TLS — todo HTTP plano. Para producción, terminar TLS en Traefik/Caddy/Nginx.
- Sin rotación ni expiración de keys.
- Sin secret manager — `.env` plano.
- Rate limit es local al proceso. Si se escalara a múltiples réplicas, habría que mover el contador a Redis.
- Logs JSON estructurados pero sin masking de PII.
- Sin RBAC granular más allá de los strings `cuentas:read`/`*:write`.

## Validaciones automatizadas

Cada push a `main` y PR ejecuta (en GitHub Actions):

- **bandit** — análisis estático de código Python en busca de vulnerabilidades comunes.
- **pip-audit** — escaneo de CVEs en dependencias pinned.
- **gitleaks** — búsqueda de secretos accidentalmente commiteados.
- **trivy** — escaneo de las imágenes Docker (HIGH y CRITICAL).
- **pytest tests/security/** — black-box tests E2E:
  - 401 sin/con API key inválida en cada tool.
  - 403 cuando user intenta operación de escritura.
  - SQL injection: el payload `'; DROP TABLE cuentas; --` no afecta la BD.
  - Validación de tipos: pydantic rechaza payloads malformados.
  - Toda llamada (incluso 403) queda en `audit_log` con latencia.

## Reportar una vulnerabilidad

Este es un demo educativo, no un proyecto en operación. Si encontraste algo interesante, abrí un issue describiendo el problema — no hay datos reales en juego.

Para proyectos en producción real: NO abrir issues públicos para vulnerabilidades. Reportar privadamente al security contact del repo o a través del [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories).

## Roadmap hacia producción

Ver el README sección "Roadmap (siguientes pasos hacia producción)".
