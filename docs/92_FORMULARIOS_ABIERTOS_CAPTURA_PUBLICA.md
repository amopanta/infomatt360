# Formularios abiertos: captura pública por token/enlace

## Objetivo

Permitir que alguien **sin cuenta** responda un formulario publicado,
usando un enlace con token -- el equivalente funcional de un enlace
público de LimeSurvey, mencionado explícitamente en la especificación
original ("Tokens/enlaces: permitir captura por token similar a
LimeSurvey para formularios públicos o controlados").

## Por qué no existía

Todos los endpoints de `backend/app/api/v1/runtime.py` exigían
`Depends(get_current_user)`; no había ningún concepto de token de
formulario público en el modelo de datos. La única forma de capturar un
registro era iniciar sesión primero.

## Modelo

`BuilderPublicLink` (`backend/app/models/builder_public_link.py`), mismo
patrón de token hasheado que `ManagerQrToken`
(`docs/74_QR_ENROLAMIENTO_GESTOR.md`) y `EmergencyAccessKey`
(`docs/90_GOBERNANZA_SOPORTE_HELPDESK.md`): el token crudo nunca se guarda,
solo su hash SHA-256 (`token_hash`).

Un mismo modelo cubre los dos casos que pide la especificación:

- **Enlace abierto** (`max_submissions=None`): respuestas ilimitadas
  mientras no expire ni se revoque -- una encuesta pública normal.
- **Enlace controlado** (`max_submissions=N`): se cierra solo después de
  `N` envíos exitosos -- útil para invitaciones de un solo uso o cupos
  limitados.

`expires_at` (opcional) y `revoked_at` (invalidación manual anticipada,
sin esperar el vencimiento) completan el modelo.

## Endpoints (`backend/app/api/v1/public_forms.py`, prefijo `/api/v1/public-forms`)

| Método | Ruta | Auth |
| --- | --- | --- |
| `POST` | `/links` | Sesión + permiso `builder.write` |
| `GET` | `/links/{template_id}` | Sesión + permiso `builder.write` |
| `POST` | `/links/{link_id}/revoke` | Sesión + permiso `builder.write` |
| `GET` | `/{token}` | **Ninguna** (público) |
| `POST` | `/{token}/submit` | **Ninguna** (público) |

`builder.write` se eligió por ser el permiso ya usado para acciones de
administración del constructor equivalentes (`acta.py`, `xlsform.py`);
`POST /links` además exige que la plantilla tenga `status="published"` --
no se puede generar un enlace público para un borrador.

### Los dos endpoints públicos

- `GET /{token}` valida el token y devuelve el mismo `RuntimeTemplate` que
  `GET /runtime/template/{id}` (se reutiliza `runtime_service.build_template_runtime`
  sin cambios: ese servicio nunca dependió de sesión, solo el router lo
  exigía).
- `POST /{token}/submit` valida el token, reserva un cupo de envío
  (ver "Concurrencia" abajo), y llama a
  `runtime_record_service.save_record()` con `user_id=None` -- el registro
  queda guardado con `submitted_by=None`, distinguible de una captura
  autenticada.

Ambos están protegidos contra fuerza bruta con el mismo patrón que
`POST /enrollment/validate` y `POST /emergency-access/redeem`
(`auth_throttle_service`, bloqueo por IP tras 20 intentos fallidos en 15
minutos).

### Concurrencia: reserva atómica del cupo

`reserve_submission_slot()` hace un `UPDATE ... WHERE submission_count <
max_submissions` condicional antes de guardar el registro, no una
lectura-luego-escritura. Sin esto, dos envíos simultáneos sobre un enlace
de un solo uso podrían pasar ambos la validación antes de que cualquiera
incrementara el contador (el mismo tipo de condición de carrera que
motivó el bloqueo optimista de `docs/85_WHATSAPP_WAHA_NOTIFICACIONES.md`
para la corrección de registros).

## Límite conocido: sin subida de archivos/firma en el enlace público

`uploadRuntimeFile()` (`frontend/src/modules/runtime/api.ts`) exige un JWT
(`Authorization: Bearer`, ver `docs/89`). Un visitante anónimo no tiene
uno, así que los campos de tipo archivo, imagen, audio, video, firma u
OCR se muestran deshabilitados en el formulario público, con la nota
"Este campo requiere iniciar sesión; no está disponible en el enlace
público" (`RuntimeField.tsx`, prop `uploadsDisabled`). El resto de tipos
de campo (texto, número, selección, GPS, repetibles, etc.) funcionan sin
restricción porque no dependen de ningún endpoint autenticado.

## Pantallas en el frontend

**Administración** -- `frontend/src/modules/admin/PublicLinksApp.tsx`
(ruta `/admin/public-links`, permiso `builder.write`): selector de
formulario del proyecto, formulario de creación (etiqueta, máximo de
respuestas, vencimiento en horas) y tabla de enlaces existentes con
estado calculado (Activo/Vencido/Agotado/Revocado) y botón "Revocar". El
token completo solo se muestra una vez, justo después de crearlo (mismo
principio que las credenciales de emergencia). Cliente API en
`frontend/src/modules/admin/publicLinksApi.ts`.

**Captura pública** -- `frontend/src/modules/publicform/PublicFormApp.tsx`
(ruta pública `/public-form/{token}`, registrada en
`frontend/src/modules/auth/AuthGate.tsx` junto a `/enroll` e `/install`):
carga el formulario sin sesión, reutiliza `RuntimeRenderer` con
`uploadsDisabled`, y muestra una pantalla de agradecimiento al enviar.
Cliente API en `frontend/src/modules/publicform/api.ts` (sin ningún
header de autenticación).

Verificado contra backend real: se generó un enlace desde
`/admin/public-links`, se abrió en una pestaña nueva **sin sesión
iniciada**, el formulario cargó y se envió una respuesta real (verificada
en la base de datos: `RuntimeRecord.submitted_by IS NULL`,
`BuilderPublicLink.submission_count` incrementado a 1).

## Pruebas

`backend/tests/test_public_forms.py`: creación de enlace exige
`builder.write` y solo permite plantillas publicadas; captura y envío
públicos de punta a punta sin ningún header de autenticación; rechazo de
token desconocido/vencido/revocado; cumplimiento del límite
`max_submissions`; revocación bloquea acceso inmediato; listar/revocar
enlaces exige `builder.write`.

## Limites conocidos

- Solo campos simples (texto, número, selección, GPS, repetibles);
  archivos/firma requieren sesión (ver arriba).
- No hay edición ni reenvío de una respuesta ya enviada por el mismo
  visitante -- cada envío crea un `RuntimeRecord` nuevo, igual que la
  captura autenticada.
- No hay límite de una respuesta por persona/dispositivo en un enlace
  abierto (`max_submissions=None`); si se necesita esa garantía, usar un
  enlace controlado (`max_submissions=1`) por invitado.
