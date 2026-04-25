.PHONY: help up down restart build logs ps clean \
        venv install \
        test test-unit test-integration test-security \
        lint fmt typecheck audit \
        psql audit-log

help:  ## Mostrar este mensaje
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Stack ────────────────────────────────────────────────────────────────────

up:  ## Levantar los 3 contenedores (build si hace falta)
	docker compose up -d --build

down:  ## Bajar y borrar volumenes (reset BD)
	docker compose down -v

restart:  ## Reiniciar mcp-fintech sin tocar BD
	docker compose restart mcp-fintech

build:  ## Rebuild las imagenes
	docker compose build

logs:  ## Tail de logs de mcp-fintech
	docker compose logs -f mcp-fintech

logs-all:  ## Tail de logs de todos los servicios
	docker compose logs -f

ps:  ## Estado de los contenedores
	docker compose ps

clean: down  ## Bajar + limpiar artefactos locales
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache htmlcov coverage.xml

# ── Desarrollo local ─────────────────────────────────────────────────────────

venv:  ## Crear venv (.venv) si no existe
	test -d .venv || python3 -m venv .venv

install: venv  ## Instalar deps de dev en el venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements-dev.txt

# ── Tests ────────────────────────────────────────────────────────────────────

test: test-unit  ## Alias de test-unit (los rapidos)

test-unit:  ## Tests unitarios (sin docker)
	.venv/bin/pytest tests/ -m unit -v

test-integration:  ## Integration tests (testcontainers postgres)
	.venv/bin/pytest tests/ -m integration -v

test-security: up  ## E2E security tests contra el stack levantado
	@echo "Esperando MCP..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
	  curl -sf -X POST http://localhost:8000/mcp/ \
	    -H "Content-Type: application/json" \
	    -H "Accept: application/json, text/event-stream" \
	    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"make","version":"1"}}}' > /dev/null && break; \
	  sleep 2; \
	done
	.venv/bin/pytest tests/security/ -m security -v

test-cov:  ## Unit tests con coverage report
	.venv/bin/pytest tests/ -m unit --cov --cov-report=html --cov-report=term

# ── Quality ──────────────────────────────────────────────────────────────────

lint:  ## ruff check
	.venv/bin/ruff check .

fmt:  ## ruff format (rewrites files)
	.venv/bin/ruff format .

typecheck:  ## mypy (informativo)
	.venv/bin/mypy api-fintech mcp-fintech

audit:  ## bandit + pip-audit
	.venv/bin/bandit -r api-fintech mcp-fintech -ll
	.venv/bin/pip-audit -r api-fintech/requirements.txt
	.venv/bin/pip-audit -r mcp-fintech/requirements.txt

# ── PostgreSQL helpers ───────────────────────────────────────────────────────

psql:  ## Abrir psql interactivo en el contenedor
	docker exec -it fintech-postgres psql -U fintech -d fintechdb

audit-log:  ## Mostrar los ultimos 20 registros de auditoria
	@docker exec fintech-postgres psql -U fintech -d fintechdb -c "\
SELECT ac.nombre, al.tool_nombre, al.status_code, al.latencia_ms, al.llamado_en::text \
FROM audit_log al JOIN api_consumers ac ON al.consumer_id = ac.id \
ORDER BY al.llamado_en DESC LIMIT 20;"
