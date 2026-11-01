# TESTIGO+ — 09: El repositorio ordenado por capas (1 nov)

**Decisión (1 nov).** Se adopta la estructura por capas que propuso la revisión del equipo (`propuestaRefactorTESTIGO+.pdf`, §9), en la rama `refactor/capas`. Solo cambian dónde viven los archivos y cómo se importan; ninguna regla, prueba ni resultado cambia de comportamiento. La rama se fusiona a `main` únicamente si pasan todas las pruebas y una corrida real de punta a punta.

## Capas

| Capa | Qué contiene | Regla |
| --- | --- | --- |
| `app/core/` | Lo que decide y lo que prueba: la política, el núcleo de decisión, la evidencia firmada y la aprobación | No llama a modelos ni al navegador; recibe lo que leyeron |
| `app/adapters/` | Lo que habla con el exterior: el cliente de Meta, el canal de píxeles (Spark + SAM) y el navegador (Playwright) | Toda salida de un modelo se valida aquí antes de llegar al núcleo |
| `app/runtime/` | Lo que ejecuta: el bucle del agente, el servicio (API, eventos, aprobación), la interfaz y el servidor MCP | Une las capas; no contiene reglas de seguridad |
| `app/security/` | El verificador independiente (`testigo verify`) | Solo lee recibos y evidencia; no depende del runtime |
| `app/sim/` | El portal simulado con los ataques | Entorno de prueba, nunca parte de la defensa |
| `app/common/` | Configuración, dinero, direcciones, reloj | Sin dependencias de otras capas |

Fuera de `app/` quedan la medición (`bench/`, `gate/`, `results/`), las pruebas transversales (`tests/`), los ejemplos (`examples/`), las herramientas (`scripts/`), la landing estática (`site/`) y los documentos (`docs/`). Las pruebas de cada módulo siguen junto a él.

## Mapa de módulos

| Antes | Ahora |
| --- | --- |
| `common/*` (menos `meta_client.py`) | `app/common/*` |
| `common/meta_client.py` | `app/adapters/meta/client.py` |
| `interceptor/channels.py` | `app/adapters/meta/channels.py` |
| `agent/driver.py` | `app/adapters/browser/driver.py` |
| `policy/compile.py`, `policy/larkspur.policy.yaml` | `app/core/policy/compile.py`, `app/core/policy/larkspur.policy.yaml` |
| `interceptor/policy.py` | `app/core/policy/model.py` |
| `interceptor/engine.py`, `instruction_filter.py`, `sensitive.py`, `events.py`, `guard.py` | `app/core/decision/` |
| `receipts/receipt.py`, `bundle.py`, `keys.py` | `app/core/evidence/` |
| `approval/*` | `app/core/approvals/` |
| `receipts/verify.py`, `receipts/cli.py` | `app/security/verifier/` |
| `agent/agent.py`, `loop.py`, `run.py`, `explain.py`, `approval.py` | `app/runtime/loop/` |
| `interceptor/service.py`, `hub.py`, `sink.py` | `app/runtime/service/api.py`, `hub.py`, `sink.py` |
| `ui/*` | `app/runtime/ui/` |
| `mcpserver/*` | `app/runtime/mcp/` |
| `portal/*` | `app/sim/portal/` |

## Comandos que cambian

| Antes | Ahora |
| --- | --- |
| `python -m agent.run` | `python -m app.runtime.loop.run` |
| `python -m receipts.cli verify …` (y `testigo verify`) | `python -m app.security.verifier.cli verify …` (`testigo verify` sigue igual) |
| `python -m policy.compile` | `python -m app.core.policy.compile` |
| `python -m portal.server` | `python -m app.sim.portal.server` |
| `python -m mcpserver` | `python -m app.runtime.mcp` |
| `uvicorn interceptor.service:app` | `uvicorn app.runtime.service.api:app` |

`make run`, `make test`, `make check-secrets` y `make gate` no cambian.

## Lo que no cambia

- Los recibos ya firmados y los resultados guardados: no dependen de rutas de código.
- Los specs 00 a 08 citan las rutas anteriores; se dejan como historia con una nota que remite a este mapa.

## Aceptación

1. Todas las pruebas pasan en la rama (495 al empezar).
2. `make run` arranca; la app y el portal responden; una corrida real con TESTIGO+ deja un recibo que `testigo verify` acepta.
3. Ningún import ni comando apunta a una ruta vieja (auditoría con búsqueda).
4. El README tiene la sección «Architecture» con el diagrama de capas y el recorrido de un pedido por los archivos.
