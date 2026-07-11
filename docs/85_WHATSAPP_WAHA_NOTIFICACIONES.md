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
hacia la pantalla de registros: `{frontend_url}/records?recordId={id}`.

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

- Sin pantalla propia en el frontend todavia (se opera por Swagger/API
  directa para consultar el historial).
- Sin recibos de lectura/entrega (requeriria webhook de WAHA).
- Solo cubre rechazo/devolucion de registros; no cubre las notificaciones
  de sincronizacion, backup o carga masiva por WhatsApp que menciona la
  arquitectura ajustada V3.
- No hay reintento automatico de envios fallidos; el ledger permite
  identificarlos para un reintento manual futuro.
