# TESTIGO+ — 12: Operación: CI, diagnóstico, guía de problemas (1 nov)

**Origen.** Segunda propuesta del compañero (`propuestaMejora1nov.pdf`). Casi todo lo que pide ya existe con pruebas (acceso solo local por Host y Origin en HTTP y WebSocket, JSON válido, 409 por corridas simultáneas, WAV validado, detector de secretos, censura de la salida, confianza en la política, recibos alterados). Se toman las cinco piezas que faltan. Se descartan: una variable `DEMO_MODE` (el sistema ya es solo local por diseño y rechaza lo externo; una variable no agrega protección) y exigir `Content-Type` (el servicio ya rechaza todo cuerpo que no sea JSON válido).

## O1. Integración continua en GitHub

`.github/workflows/ci.yml`: en cada push y pull request a `main`, Ubuntu con Python 3.12, instala `requirements.lock` y el paquete, Chromium de Playwright, `scripts/ensure_scorer_token`, y corre `scripts.check_secrets` y `pytest` (sin las pruebas `live`, que llaman a Meta). Sin secretos: nada en CI llama a modelos. El README muestra la insignia.

## O2. Diagnóstico de arranque (`make doctor`)

Además de versiones y la captura de 1280×800, una lista de comprobaciones con «ok / aviso / falla» y qué hacer: `.env` existe; variables de modelos presentes (solo nombres); llave del dueño presente; `RUNS_DIR` escribible; política activa confiable (o cuál y por qué no); puertos del portal y del servicio distintos y libres; `SCORER_TOKEN` presente. La lógica vive en `app/common/preflight.py` (probada sin red).

## O3. Guía de problemas en el README

Sección «Troubleshooting»: «PolicyNotTrusted», falta la llave, puerto ocupado, la conexión con Meta se cae a mitad de un benchmark (`--resume`), tope de gasto alcanzado, la app muestra resultados de otro escenario.

## O4. Campos desconocidos rechazados en todas las rutas JSON

Cada ruta que recibe JSON declara sus campos y responde 422 «unknown field» ante uno de más: aprobación (abrir, voz, decisión), mandato (borrador, firmar, descartar), reglas (editar). `/api/run` ya lo hacía.

## O5. `/status` dice si la política activa es confiable

`/status` agrega `policy_trusted` (sí/no), `policy_source` (comprometida o firmada aquí) y, si no es confiable, `policy_problem` con la razón. Así se ve de inmediato por qué el sistema se niega a correr.

## Aceptación

Todas las pruebas pasan en local y en CI; `make check-secrets` pasa; nada llama a modelos.
