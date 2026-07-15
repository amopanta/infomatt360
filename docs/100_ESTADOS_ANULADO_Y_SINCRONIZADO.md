# 100. Estados "anulado" y "sincronizado"

## Qué cierra esto

El hallazgo #14 de la auditoría de trazabilidad ([docs/96](96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md)) señaló que la máquina de estados de `RuntimeRecord` no cubría los 9 estados mínimos descritos en el Documento Maestro de Requerimientos v1.0. Faltaban dos:

- **`voided` ("anulado")**: invalidación formal y administrativa de un registro, distinta de `cancelled` (abandonar un borrador antes de enviarlo) y de `rejected` (no pasó control de calidad). Nunca borra el registro ni su historial — solo marca que ya no es válido, preservando la trazabilidad completa. Requiere el permiso nuevo `records.void` y es terminal: una vez anulado, ningún otro estado puede sucederlo.
- **`synced` ("sincronizado")**: confirma que un registro aprobado efectivamente llegó a un sistema externo (donante/ActivityInfo u otro conector, ver [docs/86](86_INTEROPERABILIDAD_DONANTES.md)). Requiere `records.approve` (es una continuación de la aprobación, no un permiso nuevo).

## Máquina de estados

`voided` se añadió como destino válido desde todo estado no terminal (`submitted`, `under_review`, `tech_approved`, `coordinator_approved`, `returned`, `corrected`, `approved`, `rejected`, `archived`, `synced`); desde `voided` ya no hay transiciones. `synced` solo es alcanzable desde `approved`, y desde `synced` se puede pasar a `archived` o `voided`. Ver `ALLOWED_TRANSITIONS` en `backend/app/services/review_service.py`.

## Sincronización automática vs. manual

Cuando `review_service.apply_action` aprueba un registro y el proyecto tiene una integración de donante configurada, el envío se sigue disparando fire-and-forget como antes (no bloquea la aprobación si falla). La novedad: si `integration_service.push_approved_record()` devuelve un job con `status == "sent"`, el registro avanza automáticamente a `synced` y queda un `ReviewAction` con `action="auto_synced"`. Si no hay integración configurada o el envío falla, el registro se queda en `approved` — la aprobación en sí nunca se revierte ni se bloquea por esto. También existe la transición manual "Marcar sincronizado" para los casos sin integración automática (sincronización por otro medio, confirmación manual, etc.).

## El bug que solo apareció probando en el navegador real

La implementación inicial tocó tres copias independientes de la relación estado→acciones disponibles que existen en este código (una carencia de diseño preexistente, no introducida aquí):

1. `ALLOWED_TRANSITIONS` en `review_service.py` — la máquina de estados real, la que de verdad autoriza o rechaza una transición.
2. `REVIEW_ACTIONS` en `frontend/src/modules/records/RecordsApp.tsx` — el fallback del frontend, usado solo cuando el backend no devuelve ninguna acción configurada.
3. `DEFAULT_ACTIONS` en `backend/app/services/approval_flow_service.py` — lo que el endpoint `GET /review/records/{id}/next-actions` devuelve cuando el proyecto **no** tiene un flujo de aprobación personalizado configurado (el caso común).

Las pruebas unitarias (que llaman `POST /review/actions` directo con `to_status="voided"`) pasaban sin problema porque (1) sí estaba bien. Pero el botón "Anular" nunca aparecía en la UI real: el frontend prioriza `nextActions` (que viene de (3)) sobre su propio fallback (2) en cuanto la lista no viene vacía, y (3) no se había actualizado — se detectó solo verificando en vivo contra el backend real de la demo, creando un registro y expandiéndolo en la tabla de Registros. Se corrigió agregando "Anular" (y "Marcar sincronizado" en `approved`) a `DEFAULT_ACTIONS`, y además se añadió "Anular" como acción siempre disponible incluso cuando el proyecto sí tiene un flujo de aprobación personalizado configurado (`next_actions()` ahora la agrega junto al paso configurado) — es una invalidación administrativa aparte, no otro paso más del flujo que un admin de proyecto tenga que declarar explícitamente.

Un segundo problema del mismo origen: el rol demo (`Administrador demo`, sembrado por `backend/app/cli/seed_demo.py`) tenía todos los permisos `records.*` anteriores pero no el nuevo `records.void`, así que el primer intento de anular en vivo devolvió `403`. Se agregó `records.void` a la lista de permisos sembrados y se re-ejecutó el seed contra la base de datos demo.

## Frontend

En la tabla de Registros (`/records/{template_id}`), el filtro de estado ahora incluye "Sincronizado" y "Anulado". Los badges de estado tienen estilo propio (`record-status.synced` en azul claro, `record-status.voided` en rojo/rosado, ver `frontend/src/styles.css`). El botón "Anular" aparece en el panel de flujo de revisión de todo registro no terminal; "Marcar sincronizado" solo aparece cuando el registro está `approved`.

## Pruebas

`backend/tests/test_voided_and_synced_status.py` (7 pruebas): exige el permiso `records.void` para anular (403 sin él), `voided` es terminal (transición rechazada con 400 incluso con el permiso de aprobar), registros `archived`/`rejected` igual se pueden anular, la transición manual a `synced` exige `records.approve`, un registro `synced` se puede seguir archivando o anulando, la anulación queda en el historial de acciones, y — la prueba de regresión del hallazgo anterior — `GET /next-actions` sin un flujo de aprobación configurado sí incluye "Anular" entre las acciones disponibles. `backend/tests/test_integrations.py` se extendió para verificar que una aprobación con envío exitoso al donante deja el registro en `synced`, no en `approved`. `backend/tests/test_approval_flows.py` se actualizó porque ahora `next_actions()` con un flujo configurado también incluye "Anular" junto al paso propio del flujo.

## Verificación en vivo

Contra el backend real de la demo (usuario `admin@infomatt360.demo`, proyecto `demo-project-infomatt360`): se creó un registro nuevo por API, se confirmó en el navegador real que el botón "Anular" aparecía en el panel de flujo de revisión (lo cual **no** ocurría antes de corregir `DEFAULT_ACTIONS`), se hizo clic y se recibió inicialmente `403` (permiso faltante en el rol demo — el segundo hallazgo de esta sesión), se corrigió el seed y se reintentó con éxito: el registro pasó a `voided`, quedó registrado en el historial ("void: submitted → voided") con la nota escrita en el formulario, el badge tomó el color rojo/rosado esperado (`rgb(159, 18, 57)` sobre `rgb(255, 228, 230)`, verificado por CSS computado), y al reabrir el registro ya no había ninguna acción disponible (estado terminal confirmado). Por separado, se creó y aprobó otro registro, se usó el botón "Marcar sincronizado" desde el navegador real, y quedó en `synced` con su propia entrada de historial ("mark_synced: approved → synced"), tras lo cual solo "Archivar" y "Anular" seguían disponibles. Los datos de prueba (incluyendo dos registros de prueba ya presentes en la base de datos demo desde antes de esta sesión) se eliminaron de la base de datos de la demo al finalizar.
