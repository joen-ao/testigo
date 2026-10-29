# TESTIGO+ — F7: Aprobación

28 de octubre de 2026 · Borrador para aprobación

Concreta la fila F7 del spec general: la cápsula con la que la persona aprueba lo que realmente va a pasar, vista en recortes reales de la pantalla, confirmada en voz alta y firmada con passkey. Responde la pregunta que Wonder hace antes de una acción importante. Si algo aquí contradice a `00-spec-general.md`, `01-spec-construccion.md` o `02-spec-vistas-maquetas.md`, mandan esos. Todo es simulación; la voz y el passkey son reales.

## Decisiones pendientes

| ID | Tema | Propuesta de este spec | Bloquea |
| --- | --- | --- | --- |
| F7-D1 | Qué autentica qué | La voz confirma la **intención** (qué se paga y a quién); el passkey prueba la **identidad** (quién aprueba). Son cosas distintas y la cápsula lo dice (nota del spec de vistas). | la vista 5 |
| F7-D2 | Cómo se compara la voz con la pantalla | La transcripción (Voice Transcribe) se normaliza y se compara con el monto y el destinatario **leídos de los píxeles** (F4), no del DOM. El monto en palabras se convierte a número para comparar. Coincide o no coincide; si no, el botón de passkey queda desactivado. | la vista 5 |
| F7-D3 | Biblioteca de WebAuthn del lado del servidor | A elegir al implementar; debe soportar registro y aserción de passkey en `localhost` (contexto seguro). El origen y el `rp_id` salen de `UI_ORIGIN` y `WEBAUTHN_RP_ID` (F0). | la firma de la aprobación |
| F7-D4 | Si el passkey de la demo es real o simulado | Real: WebAuthn del navegador con una passkey de plataforma, registrada una vez para la demo. Las credenciales se guardan en `.secrets/webauthn/` (F0), nunca en el repositorio. | — |

## 1. Objetivo

Cuando el motor (F6) dice que un pago cumple la política y necesita aprobación, mostrar una cápsula con dos recortes exactos de la pantalla —monto y destinatario, sin interpretación del agente—, pedir que la persona los lea en voz alta, comprobar que lo dicho coincide con lo que se ve, y recoger un passkey. Solo con voz que coincide y passkey válido se emite la aprobación, que lleva los hashes de los recortes aprobados hacia la verificación (F8) y el recibo (F9).

Fuera de alcance de F7: capturar, segmentar o decidir si hace falta aprobación (eso es F4 y F6). F7 recibe el evento `approval.requested` con sus recortes y produce `approval.granted` o un rechazo.

## 2. Entradas y salidas

**Entradas**

- De F6: `approval.requested` con el monto, el destinatario y los hashes de los recortes de monto y destinatario.
- Los PNG de esos recortes, para mostrarlos.
- El micrófono del navegador (voz) y el autenticador de plataforma (passkey).

**Salidas**

- `approval.granted` con el método (`passkey`), la transcripción de la voz y si la voz coincidió, más la firma/aserción del passkey.
- O un rechazo, con el motivo (voz no coincide, o passkey cancelado), sin aprobación.
- Los hashes de los recortes aprobados, que pasan a F8 y F9 (ya venían en el evento; F7 confirma cuáles se aprobaron).

## 3. Los cuatro estados (vista 5)

Del spec de vistas:

| Estado | Qué se ve | Qué lo produce |
| --- | --- | --- |
| Esperando voz | Los recortes, la onda y «Read aloud to confirm»; el botón de passkey inactivo | Llegó `approval.requested`, no hay voz aún |
| Voz que coincide | Indicador verde; el botón de passkey se activa | La transcripción, normalizada, coincide con los píxeles (F7-D2) |
| Voz que no coincide | La diferencia en rojo; el botón sigue inactivo | La transcripción difiere del monto o el destinatario de los píxeles |
| Aprobado | Sello verde con la hora y el hash de la aprobación | Passkey válido tras voz que coincide |

La nota pequeña de la cápsula: «Tu voz confirma lo que quieres; tu passkey prueba que eres tú» (F7-D1).

## 4. Cómo coincide la voz

- La voz se transcribe con Voice Transcribe (español), a través de `common/meta_client.py`.
- Se normaliza: minúsculas, sin puntuación, el monto en palabras a número («ciento veinte mil» → 120000).
- Se compara el número con el monto leído de los píxeles y el nombre con el destinatario leído de los píxeles (F4). Ambos deben coincidir.
- El criterio exacto (tolerancia del nombre, idioma del monto) se fija en la primera prueba con voz real; el gate de hoy ya mide voz numérica en español (95 % exacto, menos de 1,5 s).

## 5. Criterios de aceptación de F7

1. Con `approval.requested`, la cápsula muestra los dos recortes reales y queda esperando voz, con el passkey inactivo.
2. Una lectura que coincide con el monto y el destinatario de los píxeles activa el passkey; una que no coincide lo deja inactivo y marca la diferencia en rojo (criterio del 31 de oct del spec de construcción).
3. Con voz que coincide y passkey válido, se emite `approval.granted` con la transcripción y el método.
4. Un passkey cancelado o fallido no produce aprobación.
5. La voz se compara contra los píxeles (F4), nunca contra el DOM del portal.
6. El origen y el `rp_id` de WebAuthn salen de `UI_ORIGIN` y `WEBAUTHN_RP_ID`; funciona en `localhost`.

## 6. Qué se prueba con modelos reales y qué con datos de prueba

| Pieza de F7 | Con modelos reales | Con datos de prueba |
| --- | --- | --- |
| Transcripción de voz | Sí: Voice Transcribe, en el gate y en la demo | Pruebas de la normalización y la comparación con transcripciones fijas (monto en palabras → número, coincide / no coincide) |
| Passkey | Real en la demo (WebAuthn del navegador) | Pruebas del flujo del servidor con una aserción de ejemplo |
| La cápsula | — | Pruebas: dado `approval.requested`, pinta los recortes y los estados correctos |

La comparación de voz contra pantalla es la lógica propia y se prueba con datos de prueba; la transcripción real es de Voice Transcribe. El resultado de la demo sale de voz y passkey reales.

## 7. Qué del código actual se conserva

| Archivo | Se conserva | Cambia | Sale |
| --- | --- | --- | --- |
| `agent/approval.py` | Las interfaces `Approver` y `WebAuthnApprover` (el contrato) | El `WebAuthnApprover` se implementa de verdad; los aprobadores de prueba (`AutoApprover`, `DenyApprover`) se mueven a `tests/` | — |

La normalización y comparación de voz es código nuevo (propuesta: `approval/voice_match.py`), con el cliente de Voice a través de `common/meta_client.py`. La cápsula es parte de la interfaz (F11), alimentada por los eventos de F7.

## Hallazgos para los specs siguientes

1. **F4.** La comparación de voz necesita el monto y el destinatario **leídos de los píxeles**, no del DOM. F7 depende de que F4 entregue esos dos valores con su confianza.
2. **F9.** La transcripción de la voz y el método entran en el recibo (`approval`), y los hashes de los recortes aprobados son los que F9 guarda como `approved`.
3. **F1.** El mismo passkey que respalda la política (F1) es el mecanismo de identidad aquí. Conviene un solo registro de passkey para la demo, reutilizado en el mandato y en la aprobación.
