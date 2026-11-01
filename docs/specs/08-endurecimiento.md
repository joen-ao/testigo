# TESTIGO+ — 08: Endurecimiento antes de la entrega (1 nov)

**Origen.** Un compañero envió una revisión hecha con Copilot (`propuestaRefactorTESTIGO+.pdf`, 31 oct). Su diagnóstico es correcto: es un prototipo muy bueno, no un sistema de producción. Se toman las cuatro piezas que caben antes del 4 nov y no cambian la demo; se dejan fuera la reestructura del repositorio, el lenguaje propio para la política, HSM, navegador en contenedor y observabilidad de producción (razones en la conversación del 1 nov y en «Security model» del README).

## H1. Matriz de pruebas de seguridad (`tests/security/`)

Una prueba por regla, sin modelos, con el motor real, el bucle real y `testigo verify` real. Cada fila dice qué garantiza y en qué archivo vive la regla:

| Regla | Debe pasar |
| --- | --- |
| Política no cumplida (dirección o monto) | bloqueo antes del clic |
| Sin evidencia legible (región faltante o insegura, monto ambiguo) | `cannot_verify`, nunca permitido |
| Lo aprobado cambió antes del clic (revisión) | bloqueo |
| Lo aprobado cambió durante la comprobación (A4) | no hay clic |
| Código y píxeles divergen (A1, A2) | bloqueo |
| Acción sensible | siempre pide aprobación; nunca se permite sola |
| Persona rechaza o la voz no coincide | no hay pedido |
| Recibo alterado (campo, recorte, captura, firma) | `verify` falla |
| Política alterada o no firmada | no se usa (falla cerrado) |
| Fallo del modelo (excepción, salida fuera de esquema) | `cannot_verify` |

## H2. Recibo con capturas y modelos

- El recibo firmado incluye `evidence`: el sha256 de la **captura completa** aprobada y de la ejecutada (además de los recortes) y los **identificadores de modelo** configurados para la corrida (agente, lector, segmentador, voz).
- Las capturas se escriben junto al recibo (`approved_screen.png`, `executed_screen.png`). `testigo verify` comprueba sus hashes en los pasos 3 y 4 cuando están; los recibos anteriores, sin `evidence`, siguen verificando igual.

## H3. Tope de gasto por corrida

- `MAX_RUN_SPEND_USD` (por defecto 2): ninguna corrida gasta más, aunque quede saldo en `MAX_SPEND_USD`. Se cuenta en el cliente de Meta de esa corrida; WitnessBench lo reinicia en cada configuración.
- Al llegar al tope, la llamada se rechaza como `SpendCapExceeded`; el canal de píxeles lo convierte en `cannot_verify` (falla cerrado).

## H4. «Security model» en el README

Qué protege TESTIGO+, en qué confía y en qué no, qué firma el recibo y qué no garantiza, y los límites medidos (heurísticas, modelos externos, ataques previstos por nosotros, portal simulado, claves en archivos locales).

## Aceptación

Todas las pruebas pasan, `make check-secrets` pasa, nada de esto gasta en modelos.
