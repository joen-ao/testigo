# TESTIGO+ — 10: Núcleo puro, política validada y corpus de inyecciones difíciles (1 nov)

**Origen.** Lo que quedaba de la revisión del compañero (`propuestaRefactorTESTIGO+.pdf`) y vale la pena antes del 4 nov. Sin gasto en modelos.

## P1. Un núcleo de decisión sin E/S

- `app/core/decision/engine.py` separa **leer** de **decidir**:
  - `Reading`: lo que se leyó de una pantalla (regiones del canal de píxeles, líneas del código de la página, líneas pintadas, recortes, número de cuadro). Datos, sin métodos que llamen a nada.
  - `decide(policy, action, reading, latency_ms=None, confidence_min=…) -> Decision`: las reglas 1 a 4 en orden. No llama a modelos, navegador, red ni disco.
  - `compare_reread(approved_read, approved_hashes, reading, moment, …) -> (evento, lectura)`: la relectura antes y después del clic, también pura.
- `Interceptor.check` y `Interceptor.reread` quedan como envoltorios: piden la lectura al canal (`read_screen`) y llaman a la función pura. El resultado es el mismo evento de siempre.
- `tests/test_boundaries.py` agrega la regla: nada en `app/core/` importa de `app/adapters/`, `app/runtime/` ni `app/sim/`.

## P2. La política se valida al cargarla

- `app/core/policy/schema.py`: `validate_policy(data)` devuelve la lista de problemas. Exige: `version` 1; `owner` y `source` texto; `transcript` texto; `rules` lista de objetos de una sola clave entre `deliver_only`, `max_per_order_cents` y `ask_before`, sin repetir; `deliver_only` no vacía, cada destino con `name` y `address` de texto no vacíos y una dirección que se lea como dirección; `max_per_order_cents` entero (no booleano) entre 1 y 100 000 000; `ask_before` vacío o `new_address`; ningún campo de primer nivel desconocido.
- `load()` la aplica: una política mal formada lanza `PolicyInvalid` y nadie la usa (falla cerrado). La firma prueba quién la escribió; el esquema, que esté bien formada.
- El compilador del mandato y el editor de reglas validan antes de firmar.

## P3. Corpus de inyecciones difíciles

- `tests/security/injections.py`: frases de ataque que un atacante real probaría, agrupadas: oblicuas (sin verbo de orden), en español, partidas en dos líneas, dirección en palabras, con caracteres Unicode parecidos, como dato de tabla, y frases legítimas que no deben marcarse.
- `tests/security/test_injection_corpus.py` corre el filtro de instrucciones sobre todo el corpus y fija el resultado: cuáles se detectan y cuáles **se escapan** (se listan como límites conocidos, no se esconden). Si un cambio futuro mejora o empeora la detección, la prueba lo dice.
- El README («Security model») publica el conteo: cuántas de N se detectan por categoría.

## Aceptación

Todas las pruebas pasan; ninguna gasta en modelos; `make check-secrets` pasa.
