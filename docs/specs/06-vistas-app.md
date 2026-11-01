# TESTIGO+ — 06: Vistas de la app con la identidad de la landing (1 nov)

**Decisión (1 nov):** toda la app (`ui/`) adopta la identidad y los criterios de UI/UX de la landing aprobada (`site/index.html`, publicada en https://claude.ai/artifact/E7XczoqcSYdbJb7w9ZfLsk). La landing de la app (`#/`) **es** esa landing, con los números leídos de `/api/bench`. Este spec dice, vista por vista, qué cambia. Si una vista necesita explorar opciones visuales, se dibujan primero en Claude Design.

## Sistema común (tokens)

| Token | Valor | Uso |
| --- | --- | --- |
| `--ink` / `--ink-2` / `--ink-3` | `#0B0F14` / `#111821` / `#18212C` | fondo de la app, paneles, paneles elevados |
| `--line` | `#232D39` | bordes y divisores |
| `--fg` / `--muted` / `--faint` | `#E7E9EC` / `#A5AEB9` / `#6D7886` | texto, texto secundario, metadatos (≥4,5:1 sobre `--ink` salvo `--faint`, solo ≥14 px) |
| `--paper` / `--paper-ink` | `#F2EFE8` / `#1B1E22` | superficies «evidencia»: capturas, recortes, recibo |
| `--teal` / `--teal-ink` | `#3CC9A9` / `#0B6E5B` | acción principal, «verificado», paso activo |
| `--cobalt` | `#4A7BE0` | cajas de SAM y etiquetas de región |
| `--amber` / `--amber-ink` | `#F0B254` / `#8A5A00` | «retenido», «necesita a una persona», discrepancia |
| (rojo) | — | **no se usa**; un bloqueo es ámbar, no alarma |

Tipografía: Instrument Serif (títulos de vista y el veredicto), Inter Tight (todo el texto), JetBrains Mono (hashes, código, lecturas de píxeles, etiquetas pequeñas en mayúsculas). Radios: 14 px paneles, 999 px botones y chips. Botón principal: píldora `--teal` con texto `#062A22`; secundario: borde `--line`. Foco visible `--teal`. `prefers-reduced-motion` apaga todo movimiento.

**Barra común:** la misma de la landing (marca con subtítulo, cápsula de enlaces con indicador deslizante, «Code» y «Try the demo»). Dentro del demo la cápsula se reemplaza por el **progreso de 4 pasos** (puntos conectados por una línea que se llena), así no hay dos barras.

**Movimiento:** entrada suave de cada vista (`rise`, 0,5 s); cambios de estado con transición de color, nunca saltos; en «Watching», el escáner sobre la captura mientras TESTIGO+ comprueba. Solo `transform` y `opacity`.

## Vista por vista

| Vista | Ruta | Problema hoy | Cómo queda |
| --- | --- | --- | --- |
| Landing | `#/` | Es otra landing (clara, genérica), distinta de la aprobada | Porta `site/index.html` tal cual (secciones de pantalla completa, animaciones, barra). Números de WitnessBench desde `/api/bench` (escenario actual) y, si no hay, el aviso «Re-running with the current scenario». Los CTA llevan a `#/demo/rules`. |
| 1 Tus reglas | `#/demo/rules` | Tarjetas claras de texto; la política firmada no se siente como un documento | Tarjeta «papel» con la política como documento firmado: «Ship only to» (nombre + dirección en mono), «Max per order», «Ask before», sello «Signed · sha256 …» en `--teal`. Botón principal «Use these rules». «Record new rules» abre el grabador en un panel oscuro con forma de onda animada; estados (grabando, transcribiendo, borrador, rechazado, firmado) con el color del sistema. |
| 2 Correr el agente | `#/demo/run` | Tarjetas de radio genéricas | Cuatro tarjetas grandes con una miniatura de la amenaza (las mismas de la landing: código, banner, dirección falsificada; «Normal order» con una mini captura limpia), seleccionadas con borde `--teal` y marca. Interruptor «Protect with TESTIGO+» como píldora grande con texto del efecto. Un solo botón «Run the agent». Nota de costo en `--faint`. |
| 3 Mirando | `#/demo/watch` | Captura y línea de tiempo planas | Izquierda: la captura en marco «evidencia» (esquinas de recorte) con las cajas de SAM en cobalto y el escáner mientras comprueba. Derecha: línea de tiempo vertical en lenguaje simple con puntos de estado (teal ok, ámbar retenido). Cuando TESTIGO+ necesita a la persona, la **cápsula de aprobación** aparece en papel con los dos recortes, el texto a leer en voz alta, la onda y los botones Aprobar/Rechazar; borde ámbar. «Stop the run» secundario. |
| 4 Resultado | `#/demo/result` | Veredicto en rojo; evidencia larga | Veredicto grande en Instrument Serif con su color de estado (ámbar = retenido/bloqueado, teal = entregado a tu bodega verificado, ámbar oscuro con icono = entregado al atacante sin protección). Debajo, la comparación con el otro modo como dos chips. El recibo en papel con `testigo verify` como terminal animada (igual que la landing). Evidencia en acordeones con la misma estética. Acciones: «Run another», «Compare without TESTIGO+». |
| Resultados | `#/results` | Tabla clara genérica | Tres cifras grandes como la landing y una tabla por ataque (sin/con) en oscuro con números tabulares; aviso de escenario si el archivo no es del escenario actual. |
| Presentador | `#/present` | Vistas antiguas claras | Mismos tokens (sin rediseño de estructura); solo para grabar. |

## Criterios de aceptación

- Ninguna vista usa la paleta clara anterior ni rojo; todo color sale de los tokens.
- `#/` muestra la landing aprobada con datos reales o el aviso de pendiente; nada inventado.
- Cada paso del demo tiene una sola acción principal visible y el progreso arriba.
- Funciona a 375 px sin desplazamiento horizontal; foco visible; contraste 4,5:1 en texto.
- Las pruebas de `tests/test_ui.py` cubren la landing nueva, cada paso y los estados del resultado.
