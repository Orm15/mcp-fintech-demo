# Contributing

## Setup local

```bash
make install         # crea .venv y instala deps de dev
pre-commit install   # instala hooks (ruff, bandit, gitleaks)
make up              # levanta el stack docker
```

## Workflow

1. Crear branch desde `main`.
2. Editar código.
3. `make test-unit` debe pasar antes de commitear.
4. Commit con mensaje en imperativo: `Add X`, `Fix Y`, `Refactor Z`.
5. Pre-commit hooks se ejecutan automáticamente. Si fallan, fix y commit de nuevo (NO usar `--no-verify`).
6. Abrir PR contra `main`.
7. CI debe pasar verde antes de merge.

## Estructura del proyecto

```
.
├── api-fintech/         # FastAPI + Clean+Hexagonal
├── mcp-fintech/         # FastMCP server con 13 tools
├── postgres/init.sql    # schema + seed
├── tests/               # pytest (unit/integration/security)
├── docs/adr/            # Architecture Decision Records
└── .github/workflows/   # CI
```

Lectura recomendada antes de tocar código:
- [`docs/adr/0001-clean-hexagonal-architecture.md`](docs/adr/0001-clean-hexagonal-architecture.md)
- [`docs/adr/0003-protocol-vs-abc-ports.md`](docs/adr/0003-protocol-vs-abc-ports.md)

## Tests

| Tipo | Comando | Cuándo |
|------|---------|--------|
| Unit | `make test-unit` | siempre, antes de commitear |
| Integration | `make test-integration` | requieren docker; correr antes de PR |
| Security | `make test-security` | en CI; localmente si tocás auth o validaciones |

### Reglas para tests

- **Unit tests no tocan red ni filesystem.** Usan los fakes en `tests/api_fintech/unit/fakes.py`.
- **Integration tests** levantan Postgres real con `testcontainers` — son lentos (~10-30s).
- **Security tests** son black-box contra el stack levantado — los corre `make test-security` o el job `e2e-security` en CI.
- Cada bug fix idealmente añade un test que lo replica.

## Estilo

- `ruff` formatea + lintea. La configuración está en `pyproject.toml`.
- Type hints obligatorios en `domain/` y `application/`. Recomendados en el resto.
- Logs estructurados con `structlog`: `logger.info("event.name", key=value)`. NO usar f-strings en logs.
- Comentarios solo para *por qué*, no *qué*. El código bien nombrado se explica solo.

## ADRs

Decisiones arquitectónicas significativas se documentan en `docs/adr/`. Para crear uno nuevo:

1. Copiá `docs/adr/0000-template.md` a `docs/adr/NNNN-titulo-corto.md`.
2. Llená contexto, decisión, consecuencias, alternativas.
3. Actualizá `docs/adr/README.md` con el link.

## Convenciones de commit

- `add X` — nueva feature
- `fix X` — bug fix
- `refactor X` — sin cambio de comportamiento
- `docs: X` — solo documentación
- `test: X` — solo tests
- `chore: X` — deps, CI, tooling

Mensaje en español o inglés, lo importante es la consistencia dentro del PR.
