# TESTIGO+ — F3: Agente y navegador

28 de octubre de 2026 · Borrador para aprobación

Concreta la fila F3 del spec general: Wonder maneja el portal con un navegador controlado, y el interceptor se pone en medio, de modo que ninguna acción llega a la página sin pasar por él. Se puede correr con supervisor o sin él. Si algo aquí contradice a `00-spec-general.md` o `01-spec-construccion.md`, mandan esos. Todo es simulación; el agente y el navegador son reales.

## Decisiones pendientes

| ID | Tema | Propuesta de este spec | Bloquea |
| --- | --- | --- | --- |
| F3-D1 | Formato de las acciones de computer use de Wonder (punto sin confirmar del spec de construcción; prueba 2 del gate) | Aislarlo en una sola función (`agent/agent.py: parse_action`). El gate g2 guarda las respuestas crudas de Wonder; con ellas se llena esa función. El resto del sistema no depende del formato. | el agente real |
| F3-D2 | Cómo se garantiza que toda acción pase por el interceptor | El bucle es el único camino del agente al navegador: recibe la acción, la pasa por `check` (F6) y solo entonces la ejecuta en Playwright. Se mide: acciones propuestas = acciones interceptadas (gate g2, 10 de 10). | la invariante |
| F3-D3 | Qué emite el modo sin supervisor para la vista 3 | El bucle sin supervisor no corre el interceptor, así que no hay `check.result`; la vista 3 lee el pago del registro del portal. El bucle emite `agent.step` y `frame.captured` en ambos modos. | F11 |
| F3-D4 | Cómo entrega el navegador el texto del código de la página (para F5) | De `page.content()` y del árbol de accesibilidad de Playwright, junto con la captura. Es la entrada «código» de la comparación (F5-D3). | F5 |

## 1. Objetivo

Que Wonder reponga el inventario en el portal (F2) manejando un navegador real: recibir una captura, proponer una acción, y —con supervisor— pasarla por TESTIGO+ antes de ejecutarla, y recapturar después del clic. Y que todo eso se pueda correr también sin supervisor, para el «antes» de la demo. La pieza central es la invariante: nada que Wonder decida llega a la página sin pasar por el interceptor.

Fuera de alcance de F3: el canal de píxeles (F4), las reglas (F6), la aprobación (F7). F3 maneja el navegador y pone el interceptor en el camino.

## 2. Entradas y salidas

**Entradas**

- El portal (F2) servido localmente.
- La tarea para el agente (reponer el pedido DX-2041).
- El modo: con supervisor o `--no-supervisor`.

**Salidas**

- Las acciones ejecutadas en el navegador (clic, escribir).
- Por cada acción: `agent.step` y, al capturar, `frame.captured`.
- La captura y el texto del código de la página, que alimentan F4 y F5.
- El resultado de la corrida: a dónde fue el pago (del registro del portal, F2).

## 3. La invariante del gate

En modo supervisado, el bucle es el **único** camino del agente al navegador:

1. Captura la pantalla y toma el texto del código (F3-D4).
2. Le pide a Wonder la siguiente acción (una captura entra, una acción sale).
3. Pasa esa acción por `check` (F6) **antes** de ejecutarla. Si F6 bloquea, no se ejecuta.
4. Si es un pago que cumple, pide aprobación (F7); solo con aprobación se ejecuta.
5. Ejecuta la acción en Playwright y recaptura para F8.

Se mide que toda acción propuesta pase por el interceptor: acciones devueltas por Wonder = acciones interceptadas (gate g2, 10 de 10). Esa igualdad es la prueba de que el interceptor no se puede saltar.

**Sin supervisor** (`--no-supervisor`): los pasos 3 y 4 no están; el agente actúa directo. Es el modo de la vista 3 y del «antes» de WitnessBench. No deja recibo.

## 4. El formato de las acciones de Wonder

- No está confirmado cómo entrega Wonder las acciones de computer use (formato y coordenadas). Es la prueba 2 del gate.
- Todo lo que depende de ese formato vive en una sola función, `agent/agent.py: parse_action` (F3-D1). El bucle y el interceptor no la conocen.
- El gate g2 (`gate/_wonder.py`, que escribe el equipo) guarda las respuestas crudas de Wonder; con ellas se llena `parse_action`. Hasta entonces, la función se niega y el gate reporta «pendiente, formato por confirmar».
- La interceptación no depende de resolver el formato: se cuenta que cada acción devuelta pase por el gancho antes de ejecutarse.

## 5. El navegador (Playwright)

- Ventana de 1280×800, `device_scale_factor=1`, sin animaciones, en-US, zona horaria Bogotá (la configuración común de `scripts/doctor.py`, F0).
- `headless=True` en el gate y las pruebas; `headless=False` solo para grabar.
- La captura es PNG de 1280×800; sus coordenadas son las del clic.
- El texto del código sale de `page.content()` y del árbol de accesibilidad (F3-D4), como entrada «código» de F5.

## 6. Criterios de aceptación de F3

1. Con supervisor, toda acción que Wonder propone pasa por `check` antes de ejecutarse: propuestas = interceptadas (gate g2, 10 de 10).
2. En `clean`, Wonder completa el pedido sin ayuda, 3 de 3 veces (criterio del 29 de oct).
3. Sin supervisor, el agente actúa directo y el resultado se lee del registro del portal.
4. Cada acción emite `agent.step`; cada captura, `frame.captured`.
5. El formato de las acciones está aislado en `parse_action`; cambiarlo no toca el bucle ni el interceptor.
6. El texto del código de la página se entrega junto con la captura, para F5.

## 7. Qué se prueba con modelos reales y qué con datos de prueba

| Pieza de F3 | Con modelos reales | Con datos de prueba |
| --- | --- | --- |
| El bucle y la invariante | Sí: Wonder, en g2 y en la demo | Pruebas con un agente de guion (en `tests/`): propuestas = interceptadas; el bloqueo detiene la ejecución |
| `parse_action` | El formato se descubre con Wonder (g2) | Pruebas con respuestas crudas guardadas, una vez conocidas |
| El navegador | Chromium real (marcador `browser`) | — |

La invariante se prueba con un agente de guion para que sea determinista, pero «Wonder completa el pedido» y «el ataque funciona» solo valen medidos contra Wonder (F10). El agente de guion vive en `tests/` (F0) y nunca alimenta WitnessBench ni el video.

## 8. Qué del código actual se conserva

| Archivo | Se conserva | Cambia | Sale |
| --- | --- | --- | --- |
| `agent/loop.py` | La forma del bucle (agente → interceptor → navegador), el modo `--no-supervisor`, el objeto `Outcome`, la invariante | El `build_receipt` de relleno se reemplaza por el de F9; el éxito del ataque se lee del registro del portal, no del driver | — |
| `agent/driver.py` | Las interfaces `BrowserDriver` y `PlaywrightDriver` (su forma) | `PlaywrightDriver` se implementa de verdad: captura, texto del código, ejecutar la acción, recapturar | — |
| `agent/agent.py` | Las interfaces `Agent` y `ComputerUseAgent`, y `parse_action` como único punto del formato | `ComputerUseAgent` se implementa con Wonder vía `common/meta_client.py`; `parse_action` se llena con g2 | — |

El agente de guion y el driver de prueba ya están en `tests/fixtures/` (F0) y se quedan ahí. F3 implementa los reales.

## Hallazgos para los specs siguientes

1. **F4.** El navegador entrega la captura y el texto del código; F4 consume la captura, F5 el texto.
2. **F10.** La invariante y los dos modos (con y sin supervisor) son lo que WitnessBench recorre 20 veces.
3. **Gate.** Si no se puede interceptar a Wonder (prueba 2), se reconsidera el enfoque antes de seguir (riesgo del spec general). Por eso la invariante se mide hoy.
