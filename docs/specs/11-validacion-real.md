# TESTIGO+ — 11: Validación con modelos reales y WitnessBench con A4 (1 nov)

**Por qué.** Lo del 1 nov (A4, página de cuenta, A3 coherente, comparación en el clic, lecturas en paralelo, filtro con letras parecidas) solo está probado sin modelos. Los números publicados son del 31 oct, sin A4 ni página de cuenta. Este spec los mide con Meta real y publica lo que salga, aunque no favorezca la historia.

## V1. Validación dirigida (antes del benchmark)

Corridas reales, una por caso, con el portal y el canal reales; si alguna falla por un error nuestro, se arregla antes de gastar en el benchmark completo:

| Caso | Sin TESTIGO+ | Con TESTIGO+ |
| --- | --- | --- |
| A4 v1 (cambio a los 2,5 s) | ¿llega al atacante? | retenido antes de Confirm (relectura o «la pantalla cambió») |
| A3 v1 (cuenta falsificada) | ¿llega al atacante? | (lo cubre el benchmark) |

Se registra el tiempo de cada comprobación (`pixel_check_ms`) para comparar con la mediana anterior (14,2 s).

**La voz con micrófono real** no se puede probar sin una persona: queda para la prueba manual (paso 1 «Record new rules» y la aprobación del paso 3).

## V2. WitnessBench completo

- 25 configuraciones (clean, A1–A4 × 5 variantes) × 2 modos + el caso límite `a1edge`: 52 corridas, Wonder real, `--tag full`.
- Tope de gasto: `MAX_SPEND_USD` sube a 100 (decisión del 1 nov); `MAX_RUN_SPEND_USD` sigue en 2.
- La corrida anterior se archiva en `runs/bench/full_global_run2/`; el resultado nuevo se guarda en `results/witnessbench-2026-11-01-global.json`.

## V3. Publicar los números

- Landing publicada (`site/index.html`) y app (`/api/bench` lee el archivo nuevo): cifras de 20 ataques y 5 pedidos limpios, con la línea de método honesta (si Wonder resistió solo, se dice).
- README: tabla «Status» al día (1 nov) y fila de WitnessBench; `04` gana la sección de resultados del 1 nov.

## V4. Limpieza

- Se borran las 4 carpetas `.claude/worktrees/agent-*` de agentes anteriores (todo su trabajo ya estaba en `main`) y sus ramas locales.

## Aceptación

Los números publicados salen del archivo del benchmark, nunca escritos a mano; todas las pruebas pasan; `make check-secrets` pasa.
