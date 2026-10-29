# TESTIGO+ — F11: Interfaz

28 de octubre de 2026 · Borrador para aprobación

Concreta la fila F11 del spec general: las vistas del lienzo de diseño, conectadas a los eventos en vivo del sistema. La interfaz no decide nada ni llama a modelos; solo muestra lo que los demás emiten. Si algo aquí contradice a `00-spec-general.md`, `01-spec-construccion.md` o `02-spec-vistas-maquetas.md`, mandan esos. Todo es simulación.

## Decisiones pendientes

| ID | Tema | Propuesta de este spec | Bloquea |
| --- | --- | --- | --- |
| F11-D1 | Transporte de eventos | WebSocket desde el interceptor (spec de construcción). La página se suscribe a un flujo y pinta cada evento al llegar. | todo F11 |
| F11-D2 | HTML a mano o un framework | HTML, CSS y JavaScript estático servido por el interceptor (F0, sin Node). Las maquetas son HTML; se portan tal cual, sin paso de build. | — |
| F11-D3 | Resolución de la interfaz (las maquetas son 1440×900; el portal captura 1280×800) | La interfaz se diseña a 1440×900 como las maquetas; dentro, la captura del portal es una imagen de 1280×800 con las cajas de SAM dibujadas encima por coordenadas. Son dos tamaños distintos: la ventana de la demo y la captura dentro de ella. | las vistas 2 a 6 |
| F11-D4 | Si la interfaz guarda o solo muestra | Solo muestra. El estado vive en los eventos y los archivos (`receipt.json`, `bench_results.json`); la interfaz no tiene almacenamiento propio. | — |

## 1. Objetivo

Una página web que recorra el guion de la demo —portada, mandato, agente trabajando, divergencia, aprobación, verificación, recibo y WitnessBench— con cada dato saliendo de un evento o un archivo del sistema, no escrito a mano. Reutiliza el aspecto de las maquetas (sistema visual del spec de vistas) y se puede grabar de corrido para el video de 3 minutos.

Fuera de alcance de F11: producir los eventos (eso es F3 a F10). F11 los recibe y los pinta.

## 2. Entradas y salidas

**Entradas**

- El flujo de eventos del interceptor por WebSocket: `agent.step`, `frame.captured`, `check.result`, `approval.requested`, `approval.granted`, `verify.result`, `receipt.signed` (contrato de eventos, F0 hueco 8 lo completa cada feature).
- Archivos: la política firmada (vista 1), `receipt.json` (vista 7), `bench_results.json` (vista 8).
- Las capturas y los recortes PNG que referencian los eventos, servidos por el interceptor desde `runs/`.

**Salidas**

- Las pantallas renderizadas, una por vista, navegables en orden para la grabación.
- Ningún archivo ni estado propio (F11-D4).

## 3. De cada vista a su evento

Del spec de construcción, «De cada vista a su implementación real»:

| Vista | Qué pinta | De qué evento o archivo |
| --- | --- | --- |
| Portada | Título y los tres iconos | Estático |
| 1 Mandato | Onda de voz, transcripción, tarjetas de política, sello firmado | Micrófono y Voice (F1); la política firmada del archivo |
| 2 Agente | Pasos del agente y la captura en vivo | `agent.step`, `frame.captured` |
| 3 Sin TESTIGO+ | La corrida con el interceptor apagado y el pago al atacante | Corrida `--no-supervisor` (F3); el registro del portal |
| 4 Divergencia | Cajas de SAM sobre la captura y las dos columnas código/píxeles | `check.result` con `regions`, `code_only_text`, `pixels_only_text`, `latency_ms` |
| 4d No se puede verificar | El bloqueo por duda, en ámbar, con el motivo y «Ask a human» | `check.result` con `status: cannot_verify` |
| 5 Aprobación | Los dos recortes, la onda de voz, la transcripción, el passkey | PNG recortados, Voice (F7), WebAuthn |
| 6 Después del clic | Recortes de antes y después y su comparación | `verify.result` con ambos grupos de hashes |
| 7 Recibo | La tarjeta del recibo y la terminal de `testigo verify` | `receipt.json` y la CLI en vivo |
| 8 WitnessBench | El número y las barras | `bench_results.json` |

## 4. Cómo se dibujan las cajas y los recortes

- La captura del portal llega como imagen de 1280×800. Las cajas de SAM (`regions` en `check.result`) traen `box: [x0,y0,x1,y1]` en coordenadas de esa imagen; la interfaz las dibuja encima por posición, con el color del estado (azul para marcadas, rojo para la divergencia).
- Los recortes de evidencia (vistas 5 y 6) son los PNG que el interceptor recortó, servidos desde `runs/`, con su hash corto debajo (del evento, no inventado).
- El sistema visual (colores, tipografía, íconos con texto) sale del spec de vistas y es el mismo de las maquetas. Las correcciones de las maquetas (spec de construcción) ya están aplicadas en el lienzo y se portan con ellas.

## 5. Criterios de aceptación de F11

1. Con el portal, el interceptor y una corrida en marcha, la interfaz recorre las 8 vistas y la portada sin tocar el código (criterio del 1 de nov del spec de construcción).
2. Cada dato visible viene de un evento o un archivo; no hay cifras escritas a mano en la vista 4, 6, 7 ni 8.
3. Las cajas de SAM caen sobre los elementos correctos de la captura (coordenadas del evento).
4. La vista 7 corre `testigo verify` de verdad y muestra su salida real.
5. La vista 8 lee `bench_results.json`; mientras no exista, muestra el aviso de «ejemplo» y no cifras como verdaderas.
6. La interfaz no es el protagonista: no hay un tablero de control; el centro son los bloqueos en vivo (vistas 4 a 6), y el recibo y los números van al final (spec de vistas, «qué no maquetar»).

## 6. Qué se prueba con modelos reales y qué con datos de prueba

| Pieza de F11 | Con modelos reales | Con datos de prueba |
| --- | --- | --- |
| Pintar eventos | No aplica (no llama a modelos) | Pruebas: dado un evento de ejemplo, la vista pinta los campos correctos; las cajas caen en las coordenadas dadas |
| El recorrido completo del video | Sí: sobre una corrida real (F10) | — |

La interfaz no llama a ningún modelo. Sus pruebas usan eventos de ejemplo solo para comprobar que pinta bien; el video sale de una corrida real.

## 7. Qué del código actual se conserva

No hay código de interfaz todavía. F0 dejó el servicio del interceptor (`interceptor/service.py`) con una página de estado y el lugar donde se montan el WebSocket y los estáticos. F11 agrega la carpeta `ui/` (HTML, CSS y JS estático) y el WebSocket en el servicio. Las maquetas del lienzo son la guía visual; no son código que se importe, se reconstruyen como HTML.

## Hallazgos para los specs siguientes

1. **Contrato de eventos (F0 hueco 8).** F11 necesita que cada evento tenga sus campos fijos. `check.result` ya está definido; `agent.step`, `frame.captured`, `approval.*`, `verify.result` y `receipt.signed` los cierra cada feature que los emite. F11 consume lo que haya; si falta un campo, se pide primero en el spec de esa feature.
2. **Vista 3.** Mostrar la corrida sin supervisor y el pago al atacante necesita que el interceptor pueda emitir eventos también en modo `--no-supervisor` (o que la vista lea el registro del portal). Decidirlo en F3.
3. **Servir `runs/`.** La interfaz sirve capturas y recortes desde `runs/`, que es git-ignorada; en la demo están presentes localmente, nunca en el repositorio.
