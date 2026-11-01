# TESTIGO+ — 05: Landing (spec de mejora, 1 nov)

## Diagnóstico de la landing actual

| Problema | Por qué importa |
| --- | --- |
| Plantilla genérica de SaaS: héroe, tres tarjetas, cuatro pasos, cifras | No se distingue de cualquier producto; el jurado no recuerda nada |
| El producto no se ve: la única imagen es una tarjeta de «Blocked» | La idea central (el agente y la persona ven cosas distintas) no se demuestra, se cuenta |
| No hay un momento «ajá» | Lo más fuerte del proyecto es que el texto escondido existe y no se ve; la página nunca lo revela |
| Los pasos son texto | La arquitectura (agente → TESTIGO+ → navegador, con los cuatro modelos de Meta) no se entiende de un vistazo |
| El recibo y `testigo verify` son una línea al pie | Son la prueba de que no hay que confiar en nosotros; merecen una sección |
| No dice qué no hace | Un jurado técnico confía más en un límite medido que en un 100 % |
| Ejemplo local (Doña Marta, Bogotá) | Pasa al escenario global de `04-escenario-global.md` |
| Tipografía y color neutros, sin jerarquía fuerte | Se ve como un borrador |

## Objetivo

En 20 segundos de scroll, cualquier persona entiende: (1) una página puede darle a un agente una orden que la persona no ve; (2) TESTIGO+ mira los píxeles y los compara con reglas firmadas; (3) cada decisión deja un recibo verificable; (4) está medido con modelos reales, con sus límites.

## Estructura

1. **Barra:** logo, «How it works», «Attacks», «Results», «Verify», botón «Try the demo».
2. **Héroe:** titular corto con tensión («Your agent reads the page. TESTIGO+ reads the screen.»), una línea de apoyo y dos botones. A la derecha, **la pantalla de revisión de Crestline Wholesale** con las cajas de SAM (total, dirección, botón) y el sello de bloqueo; el campo «Ship to» muestra `Larkspur Market · 88 Mill Street` y la regla firmada `120 Harbor Road, Unit 4`.
3. **«What the agent reads vs. what you see»** (el momento «ajá»): dos columnas de la misma página. Izquierda, el código con la línea escondida resaltada; derecha, la pantalla limpia. Un control «Reveal» (interactivo) muestra la línea pintada en el banner (A2), apenas visible, y la marca.
4. **Tres ataques** como tres miniaturas de pantalla, no como tarjetas de texto: oculto en el código, pintado en la imagen, dirección adulterada bajo el nombre de la empresa. Cada una dice cómo la atrapa TESTIGO+ (divergencia código/píxeles, texto solo en píxeles, dirección fuera de la política).
5. **Cómo funciona**: un diagrama horizontal (agente Muse Wonder → TESTIGO+ [SAM 3.1 encuentra, Muse Spark lee, política firmada] → navegador), con la persona aprobando por voz (Muse Voice) en el punto de confirmación. Debajo, los cuatro pasos en una línea cada uno.
6. **Recibo verificable**: a la izquierda una tarjeta de recibo en monoespaciada (id, política, hashes de los recortes, firma); a la derecha una terminal con `testigo verify receipt.json` → «Signature valid · evidence matches» y el caso alterado «Evidence mismatch at step 4».
7. **Resultados (WitnessBench)**: tres cifras grandes en conteos, leídas del archivo del benchmark en la app (en el diseño, marcadores `[X] of 15` hasta la nueva corrida), y una línea de método: modelos reales, 20 configuraciones × 2 modos.
8. **Lo que no hace (límites)**: tres a cuatro líneas honestas (unos 15 s por comprobación; el texto escrito solo en palabras puede escapar al filtro; pide a una persona cuando no puede leer; no reemplaza la autenticación).
9. **Cierre**: «See it stop an attack» con el botón al demo y el enlace al repositorio.
10. **Pie**: simulación, sin marcas reales; modelos de Meta usados.

## Dirección visual

- Identidad: azul marino `#0E2A4F` / `#104281`, acento `#2A78D6`, fondo cálido `#FAFAF8`; rojo `#A32020` solo para el bloqueo y verde `#0B6B3A` solo para «verificado».
- Tipografía: display con carácter para titulares (p. ej. «Space Grotesk» 700) y sans del sistema para el cuerpo; monoespaciada para código, recibo y terminal.
- Las pantallas del portal se dibujan en markup con aspecto de navegador real; las cajas de SAM en azul con etiqueta y confianza, como en la app.
- Sin degradados decorativos, sin emojis, sin tarjetas con borde lateral. Contraste 4,5:1; botones de 44 px o más; funciona a 375 px de ancho.

## Criterios de aceptación

- El ejemplo es el de `04` (Larkspur Market, Crestline Wholesale, Dock 9 Storage, USD); ninguna mención a Doña Marta, Bogotá ni COP.
- La sección 3 deja ver la línea escondida y la pintada sin leer ningún párrafo.
- Ninguna cifra inventada: los resultados son marcadores hasta la corrida nueva; en la app se leen de `/api/bench`.
- La app (`ui/`) porta este diseño en la ruta `#/` cuando esté aprobado.

## Dirección elegida (1 nov)

El equipo eligió la **opción A («Forense»)** entre tres direcciones dibujadas en Claude Design, con una paleta de más confianza: fondo tinta `#0D1117`, papel cálido `#F4F1EA`, acento verde azulado de «verificado» `#3CC9A9` (`#0E7C66` sobre claro), cajas de SAM en cobalto `#3B6FD4` y ámbar `#F0B254` para «retenido»; sin rojo de alarma. Tipografía: Instrument Serif (titulares), Inter Tight (cuerpo), JetBrains Mono (evidencia, código, recibo).

Estructura de página de servicio: barra con «Talk to us» y «Try the live demo»; héroe con la captura como evidencia; **demo en video** (segunda sección, se hace con HyperFrames cuando el rediseño del producto esté completo; hoy es un marcador con capítulos); el problema en tres «exhibits»; cómo funciona en cuatro pasos (firmar, atestiguar, confirmar, probar); capacidades; verificación del recibo; resultados de WitnessBench (marcadores hasta la nueva corrida); preguntas y límites medidos; cierre con llamada a la acción. Diseño: https://claude.ai/artifact/JCD7qEFWBLFQ8mXchcdSSh (tablero «Landing · A, trusted palette»).
