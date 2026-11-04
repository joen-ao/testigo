# TESTIGO+ — 13: El recibo mientras se firma (4 nov)

**Origen.** Grabación del demo, 4 nov (corrida `runs/2026-11-04/145243_clean_v1_sup`). Pedido normal, protegido, aprobado escribiendo. El agente confirmó a las 14:56:13 y TESTIGO+ firmó el recibo a las 14:56:37: 24 s después, porque antes de firmar vuelve a leer la pantalla del resultado (`verify.result` después del clic). El botón «See the result» aparece con `order.confirmed`. En esos 24 s la tarjeta del recibo del paso 4 decía:

> No receipt for this run: you approved, but TESTIGO+ never let the agent click Confirm, so no order was placed to sign for.

Eso es falso: el agente sí hizo clic, el pedido llegó a tu bodega y el recibo se firmó y verifica (`testigo verify` → «Signature valid»). El texto venía del commit `1d14752` (caso A4: aprobaste pero TESTIGO+ no dejó confirmar) y se mostraba para cualquier corrida aprobada sin `receipt.signed`, aunque ya hubiera `order.confirmed`.

## R1. Estados de la tarjeta sin `receipt.signed`

`receiptCard` (`app/runtime/ui/flow.js`) decide por lo que ya pasó en la corrida, no solo por la aprobación:

| Lo que pasó | La tarjeta dice |
| --- | --- |
| Hay `order.confirmed`, el log trae `receipt not signed/written` | «The order went through, but the receipt could not be signed on this machine.» |
| Hay `order.confirmed` y la corrida sigue (o no se sabe si terminó) | «Signing the receipt…»: TESTIGO+ vuelve a leer la pantalla después del clic y luego firma; tarda cerca de medio minuto. La barra dice «signing…». |
| Hay `order.confirmed` y la corrida terminó sin recibo | «The order went through, but this run ended without a receipt.» |
| Aprobaste, sin `order.confirmed`, la corrida sigue | «You approved. Waiting for the agent to confirm the order; the receipt is signed after that.» |
| Aprobaste, sin `order.confirmed`, la corrida terminó (A4) | El texto del commit `1d14752`: TESTIGO+ nunca dejó hacer clic. |
| No aprobaste | «Receipts are signed only for an order you approved.» (igual que antes) |

«La corrida terminó» = el proceso que lanzó esta página es el de esta corrida (mismo escenario y `run.started` dentro de su vida, con 5 s de margen) y está en `finished`, `failed` o `cancelled`. Un proceso de una corrida anterior no cuenta: al probar el arreglo el 4 nov, el proceso ya terminado de la corrida A3 hacía decir «this run ended without a receipt» a una corrida nueva. En una corrida lanzada desde la terminal no se sabe; ahí se dice «Signing…» o «Waiting…», nunca algo falso.

## R2. Cuando llega el recibo

Sin cambios: `receipt.signed` ya vuelve a dibujar y carga el recibo (`loadReceipt`). La tarjeta pasa sola de «Signing the receipt…» a «Signed receipt» con «Verify receipt».

## Aceptación

- Una prueba en `tests/test_ui.py` comprueba que `flow.js` ya no muestra el texto de A4 cuando hay `order.confirmed`, y que tiene el estado «Signing the receipt».
- Todas las pruebas pasan; `make check-secrets` pasa; nada llama a modelos.
- En el navegador, con los eventos de la corrida del 4 nov repetidos hasta `order.confirmed`, el paso 4 dice «Signing the receipt…»; con `receipt.signed`, muestra el recibo firmado.
