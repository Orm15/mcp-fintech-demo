# ADR-0001: Clean Architecture + Hexagonal para api-fintech

- **Estado:** Aceptado
- **Fecha:** 2026-04-25

## Contexto

`api-fintech` expone endpoints HTTP y persiste datos en PostgreSQL. La primera versión usaba una arquitectura plana (`models.py`, `routes.py`, `db.py`) con dependencia directa a la BD desde los handlers.

Riesgos identificados:
- Lógica de negocio acoplada a FastAPI y a psycopg2 — imposible testear sin levantar todo.
- Cambiar de PostgreSQL a otra fuente requiere reescribir handlers.
- No hay frontera explícita entre "qué hace el sistema" y "cómo lo hace".

## Decisión

Adoptar **Clean Architecture combinada con Hexagonal (Ports & Adapters)** con la siguiente estructura:

```
api-fintech/
├── domain/              # Entidades + ports — capa más interna
│   ├── entities/        # Pydantic models (Cuenta, Transferencia, ...)
│   ├── ports/           # Protocols (ICuentaRepository, ...)
│   └── exceptions.py
├── application/         # Casos de uso — orquesta entidades y ports
│   └── use_cases/
├── adapters/
│   ├── primary/http/    # FastAPI routers + DTOs de request
│   └── secondary/postgres/  # Implementación de los ports
└── infrastructure/      # Pool, container DI, lifespan FastAPI
```

**Regla de dependencia:** `adapters → application → domain`. Las capas internas nunca importan las externas.

**Ports como `Protocol` + `@runtime_checkable`** (no ABC): structural subtyping, sin herencia explícita. Ver [ADR-0003](0003-protocol-vs-abc-ports.md).

**DI por factory functions** en `infrastructure/container.py` + `Depends()` de FastAPI. Los use cases reciben repositorios por constructor.

## Consecuencias

**Positivas:**
- Use cases testables al 100% con fakes en memoria — los unit tests corren en <0.5s sin Docker.
- Cambiar de PostgreSQL a otra fuente solo requiere swappear los adapters secundarios en `container.py`. La BD se reemplazó por adapters in-memory durante una iteración previa sin tocar `domain/` ni `application/`.
- Frontera explícita entre "qué" (domain + application) y "cómo" (adapters + infrastructure).

**Negativas:**
- Más archivos y boilerplate vs un script plano. Para un API con 9 endpoints es overkill puramente práctico, pero el demo apunta a ilustrar el patrón.
- El equipo necesita entender la regla de dependencia para no romper la arquitectura.

**Neutras:**
- Los DTOs de request (Pydantic) viven en `adapters/primary/http/` — no en `domain/`. Esto evita que el dominio dependa del transporte.

## Alternativas consideradas

- **Plana (`models.py` + `routes.py`)** — simple para apps cortas, pero acopla lógica con framework y BD. Descartada por valor pedagógico.
- **Solo Clean (sin Hexagonal explícito)** — Clean ya implica ports/adapters; combinarlo con la nomenclatura hexagonal (`primary`/`secondary`) hace más obvio el flujo.
- **Repository pattern con ABC** — equivalente funcional, más verboso. Ver ADR-0003.

## Referencias

- Robert C. Martin, "Clean Architecture" (2017)
- Alistair Cockburn, "Hexagonal Architecture" (2005)
