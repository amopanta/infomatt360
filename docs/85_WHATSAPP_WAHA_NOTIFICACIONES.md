# Notificaciones WhatsApp via WAHA

## Objetivo

Canal de notificacion adicional (junto a `InternalMessage` y `MailProfile`)
para el caso concreto que especifica el documento original: cuando un
registro es rechazado o devuelto para correccion, ademas del mensaje
interno ya existente, se envia un WhatsApp al gestor con un enlace directo
para corregirlo.

## Adaptacion respecto al documento original

El documento original describe un "Enlace Magico" con esquema
`infomatt://correccion?id=...&campo=...`, pensado para una app movil nativa
que registre ese protocolo. La arquitectura real de InfoMatt360 es
web + PWA + escritorio Electron (ver
[82_APLICACION_ESCRITORIO_ELECTRON.md](82_APLICACION_ESCRITORIO_ELECTRON.md),
[83_PWA_OFFLINE_INSTALABLE.md](83_PWA_OFFLINE_INSTALABLE.md)), sin app
nativa que capture ese esquema. El enlace se adapta a una URL HTTPS real
hacia la pantalla de registros: `{frontend_url}/records/{template_id}?recordId={id}`,
y si el revisor indico el campo puntual con el error
(`ReviewActionCreate.rejected_field_name`), agrega `&campo={campo}` -- el
equivalente funcional del `&campo=...` del esquema nativo original, pero
resuelto como parametro de consulta real sobre una URL que el frontend
efectivamente interpreta (ver "Deep-link al campo especifico" abajo).

**Correccion de paso**: el enlace anterior (`/records?recordId={id}`, sin
`template_id`) no funcionaba en absoluto -- el frontend no leia `recordId`
de la URL en ningun punto, asi que el "enlace magico" original solo
llevaba a la lista generica de formularios. El enlace corregido incluye el
`template_id` (ya disponible en el registro) y el frontend ahora si
resuelve `recordId`/`campo` de la URL.

Tambien quedan fuera de este alcance minimo los recibos de lectura/entrega
(exigirian configurar un webhook de WAHA de vuelta hacia el backend) y las
notificaciones de sincronizacion/backup/carga masiva por WhatsApp que
menciona la arquitectura ajustada V3 — solo se cubre el rechazo/devolucion
de registros, el unico caso descrito con comportamiento concreto en la
especificacion tecnica original.

## Modelo

`WhatsAppNotification` (`backend/app/models/whatsapp.py`): ledger
inmutable de intentos de envio — `project_id`, `recipient_user_id`,
`recipient_phone`, `message`, `reference_record_id`, `status`
(`sent`/`failed`/`skipped`), `error`, `created_at`. Un reintento manual
crearia una fila nueva, no actualiza una existente.

## Estado por defecto: inactivo

Sin `WAHA_BASE_URL` configurado (`backend/app/core/config.py`), el canal
queda inactivo: `whatsapp_service.send_text()` no intenta ninguna
peticion HTTP y registra el intento con `status="skipped"`. El flujo de
rechazo de un registro funciona exactamente igual con o sin WAHA
configurado — el canal WhatsApp es un extra, nunca un requisito.

## Disparador

El enganche vive en `review_service._add_status_notification()`
(`backend/app/services/review_service.py`), el mismo metodo que ya
enviaba el `InternalMessage` en cada cambio de estado. Si
`payload.to_status` es `"rejected"` o `"returned"` y el dueño del registro
tiene `User.phone`, se llama `whatsapp_service.send_text()` ademas del
mensaje interno. Un fallo de red hacia WAHA (timeout, servidor caido) no
interrumpe ni revierte la accion de revision — se registra como
`status="failed"` en el ledger y el flujo continua.

## Cliente WAHA

`backend/app/services/whatsapp_service.py` usa `httpx` sincrono (no
`httpx.AsyncClient`) para mantener el mismo estilo que el resto de
servicios HTTP salientes del backend (ver
[79_CONECTOR_GOOGLE_DRIVE.md](79_CONECTOR_GOOGLE_DRIVE.md)): los
endpoints de FastAPI son sincronos (`def`, no `async def`).

```
POST {WAHA_BASE_URL}/api/sendText
Headers: X-Api-Key: {WAHA_API_KEY}   (si esta configurada)
Body: { "chatId": "<numero>@c.us", "text": "...", "session": "{WAHA_SESSION}" }
```

El numero de telefono guardado en `User.phone` se normaliza a solo
digitos y se le agrega el sufijo `@c.us` que exige WAHA para chats
individuales.

## Variables de entorno

| Variable | Default | Descripcion |
| --- | --- | --- |
| `WAHA_BASE_URL` | `""` (vacio = inactivo) | URL base de la instancia WAHA, ej. `https://waha.midominio.com` |
| `WAHA_API_KEY` | `""` | API key de la instancia, si esta protegida |
| `WAHA_SESSION` | `"default"` | Nombre de la sesion de WhatsApp configurada en WAHA |

## Endpoint

`GET /api/v1/whatsapp/notifications/project/{project_id}` — historial de
envios del proyecto. Requiere alguno de `messages.read`, `records.review`
o `records.approve`.

## Pantalla en el frontend

`frontend/src/modules/admin/WhatsAppApp.tsx` (ruta `/admin/whatsapp`,
mismos permisos que el endpoint): resumen de conteos por estado
(enviado/fallido/omitido), filtro por estado, y tabla con fecha,
destinatario, registro relacionado, mensaje (con el enlace magico
incluido) y error si aplica. Si todas las notificaciones estan
`omitidas`, muestra un aviso explicando que falta configurar
`WAHA_BASE_URL`. Cliente API en
`frontend/src/modules/admin/whatsappApi.ts`. Verificado en navegador real
contra un registro rechazado real: aparece con el motivo exacto del
"omitido" cuando no hay proveedor configurado.

### Deep-link al campo especifico (`RecordsApp.tsx`)

Al elegir "Rechazar" o "Devolver" en el panel de revision
(`frontend/src/modules/records/RecordsApp.tsx`), aparece un selector
"Campo con error (para el enlace de correccion por WhatsApp)" poblado con
los `field_name` del registro; el valor elegido viaja como
`rejected_field_name` en `POST /review/actions`.

Al abrir el enlace del WhatsApp (`/records/{template_id}?recordId=X&campo=Y`),
`RecordTable` lee `recordId`/`campo` de la URL, consulta ese registro
puntual con `GET /runtime/record/{id}` (sin depender de en que pagina de
la lista paginada caiga) y lo muestra en una tarjeta destacada arriba de
la tabla ("Registro señalado para corrección"), con el campo indicado por
`campo` resaltado (`scrollIntoView` + contorno rojo) para que el gestor lo
ubique de inmediato sin tener que leer todo el formulario de nuevo.

Verificado en navegador real: se rechazo un registro submitted indicando
el campo `ubicacion`, el historial reflejo "Campo: ubicacion", y al abrir
la URL `/records/{template_id}?recordId={id}&campo=ubicacion` la tarjeta
destacada aparecio con el campo `ubicacion` resaltado
(`outline: 3px solid rgb(214, 69, 69)`, confirmado via el DOM real).

### Correccion de paso: el enlace mágico ahora corrige de verdad

**El hallazgo**: hasta este punto, el enlace mágico permitía *ver* el
campo señalado y marcar el registro como `"corrected"`, pero no existía
ningún camino de codigo que realmente cambiara el valor de un campo ya
guardado -- `runtime_record_service.save_record()` siempre crea una fila
nueva, nunca actualiza una existente, y ningun router (`records.py`,
`runtime.py`) exponia un `PUT`/`PATCH`. En la práctica, un gestor que
abría el enlace solo podía leer el error y marcar "corregido" sin haber
corregido nada.

`PATCH /api/v1/runtime/record/{record_id}/correction`
(`runtime_record_service.correct_field()`, permiso `records.write`) cierra
esa brecha:

- Solo se permite mientras el registro esta en estado `"returned"` -- un
  registro aprobado, rechazado o archivado sigue siendo inmutable, igual
  que el resto del sistema (ver el ledger inmutable de ERP en
  [84_ERP_HEADLESS_INVENTARIO_NOMINA.md](84_ERP_HEADLESS_INVENTARIO_NOMINA.md)).
- Actualiza o crea el `RuntimeRecordValue` del campo indicado (upsert real,
  el primero en todo el sistema sobre un valor ya existente).
- **Control de edicion concurrente**: `RuntimeRecord.lock_version`
  (migracion `0057`) es un bloqueo optimista. El cliente debe enviar
  `expected_lock_version` con el valor que vio la ultima vez que cargo el
  registro; si otro usuario ya lo corrigio mientras tanto, el backend
  responde `409 Conflict` con un mensaje claro en vez de sobrescribir en
  silencio el cambio ajeno. Cada correccion exitosa incrementa
  `lock_version` en 1.

En el frontend (`RecordsApp.tsx`), cada campo de la tarjeta destacada
tiene un boton "Corregir" que lo vuelve editable (solo para valores
simples -- texto/numero/booleano; campos complejos como fotos o firmas
muestran una nota indicando que deben recapturarse desde el formulario
original, no se editan aqui). Al guardar, se llama a
`correctRecordField()` (`frontend/src/modules/records/api.ts`); si el
backend responde `409`, el mensaje de error se muestra tal cual para que
el gestor recargue el registro antes de reintentar.

Verificado en navegador real (con dos "usuarios" simulados: la UI y una
llamada API directa): se corrigio `telefono_contacto` desde la UI y el
valor se reflejo de inmediato en la tarjeta; luego, con el `lock_version`
ya desactualizado en el navegador, un segundo intento de correccion sobre
otro campo fue rechazado con `409` y el mensaje "El registro fue
modificado por otro usuario... recarga el registro y vuelve a intentar",
confirmando que el bloqueo optimista evita la sobrescritura silenciosa.

## Como levantar una instancia WAHA para activarlo

WAHA es open-source y se levanta con Docker:

```powershell
docker run -it --rm -p 3000:3000 devlikeapro/waha
```

Luego, desde la UI de WAHA (`http://localhost:3000`) o su API, se crea una
sesion (por defecto `"default"`) y se escanea el codigo QR con el
WhatsApp que va a enviar las notificaciones. Con la sesion en estado
`WORKING`, basta configurar en `backend/.env`:

```
WAHA_BASE_URL=http://localhost:3000
WAHA_SESSION=default
```

(`WAHA_API_KEY` solo si la instancia esta protegida con autenticacion).

## Limites conocidos

- Sin recibos de lectura/entrega (requeriria webhook de WAHA).
- Solo cubre rechazo/devolucion de registros; no cubre las notificaciones
  de sincronizacion, backup o carga masiva por WhatsApp que menciona la
  arquitectura ajustada V3.
- No hay reintento automatico de envios fallidos; el ledger permite
  identificarlos para un reintento manual futuro.
- La correccion via enlace magico solo edita valores simples
  (texto/numero/booleano) desde la tarjeta destacada; fotos, firmas, GPS u
  otros campos complejos deben recapturarse desde el formulario original.
- Solo se puede corregir un registro en estado `"returned"` -- no hay
  edicion general de participantes ni de registros en otros estados
  (aprobado, rechazado, archivado siguen siendo inmutables).

## Pruebas

`backend/tests/test_runtime_record_correction.py`: corrige un valor
existente e incrementa `lock_version`, crea un valor para un campo que no
existia todavia, **rechaza una segunda correccion con `expected_lock_version`
desactualizado (409, control de edicion concurrente)**, rechaza corregir
un registro que no esta en `"returned"`, exige el permiso `records.write`,
y responde `404` para un `record_id` inexistente.
