# ADR-0003: Ports como `Protocol` + `@runtime_checkable` (no ABC)

- **Estado:** Aceptado
- **Fecha:** 2026-04-25

## Contexto

Los ports del dominio (`ICuentaRepository`, etc.) definen el contrato que cualquier adapter secundario debe cumplir. Python tiene dos formas idiomáticas de expresar esto:

1. **ABCs** (`abc.ABC` + `@abstractmethod`) — herencia explícita: los adapters deben heredar de la ABC.
2. **`typing.Protocol`** — structural subtyping: cualquier clase con la firma correcta cumple el contrato sin herencia.

## Decisión

Usar **`Protocol` con `@runtime_checkable`**:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ICuentaRepository(Protocol):
    def get_cliente(self, cliente_id: str) -> Cliente | None: ...
    def get_cuenta(self, cuenta_id: str) -> Cuenta | None: ...
    ...
```

Los adapters **no heredan** de `ICuentaRepository` — solo implementan los métodos:

```python
class PostgresCuentaRepository:
    def get_cliente(self, cliente_id: str) -> Cliente | None:
        ...
```

## Consecuencias

**Positivas:**
- **Cero acoplamiento estructural**: el `domain/` no se importa desde los adapters. Inversión de dependencia 100% — el adapter "sabe" cumplir un contrato pero nunca importa el contrato.
- **Tests con fakes triviales**: `class FakeCuentaRepo: def get_cliente(...)...` y listo. No hay que heredar nada.
- **Idiomatic Python moderno**: la PEP 544 promueve duck typing tipado.
- **`@runtime_checkable`** permite validar conformancia con `isinstance(repo, ICuentaRepository)` cuando se necesita.

**Negativas:**
- Si el adapter cambia accidentalmente la firma de un método, no hay error de import — solo falla en runtime cuando se llama. Mitigación: tests + mypy.
- Algunos IDEs muestran "implementa este protocolo" con menos prominencia que "hereda de esta ABC".

**Neutras:**
- En unit tests no es estrictamente necesario el `@runtime_checkable` — los fakes funcionan igual sin él.

## Alternativas consideradas

- **ABC con `@abstractmethod`** — funciona, pero acopla el adapter al dominio (`from domain.ports... import ICuentaRepository` + herencia). Para un demo que quiere ilustrar inversión de dependencia limpia, Protocol es superior.
- **No tipar los ports** (duck typing puro) — se pierde el contrato explícito, los tests no documentan el contrato y mypy no ayuda.

## Referencias

- [PEP 544 — Protocols](https://peps.python.org/pep-0544/)
- [Python typing — Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol)
