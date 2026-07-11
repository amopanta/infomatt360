# Asset lock por dispositivo y sesion extendida para campo

## Objetivo

Cerrar dos brechas detectadas al auditar el codigo contra la especificacion
original (`InfoMatt_Core_Documentacion_Maestra_Definitiva.pdf` e
`infomatt_core_arquitectura_ajustada_v2.pdf`):

1. El campo `device_fingerprint` del enrolamiento por QR se registraba pero
   nunca se comparaba ni bloqueaba nada -- no habia "asset lock" real.
2. Todos los tokens JWT usaban la misma expiracion corta (60 min), sin la
   variante extendida que el documento maestro pide explicitamente para
   "dispositivos moviles de los gestores rurales" (10 horas).

## Lo que dice la especificacion original

> "Escaneo Serial Fisico + Firma Digital (MDM Bypass & Asset Lock)" /
> "Asignacion estricta del activo al gestor en campo" (tabla
> `core_dispositivos`, `InfoMatt_Core_Documentacion_Maestra_Definitiva.pdf`).

> "Los tokens emitidos para los dispositivos moviles de los gestores
> rurales poseen un tiempo de vida extendido de 10 horas exactas para
> garantizar que la sesion no expire durante la jornada de campo sin
> conectividad" (`Especificaciones_Tecnicas_InfoMatt_360.pdf`, modulo 4.2).

## Asset lock por dispositivo

### Modelo

`User.locked_device_fingerprint` y `User.device_lock_updated_at`
(`backend/app/models/identity.py`, migracion
`0055_device_asset_lock_and_field_tokens.py`). No se creo una tabla
`core_dispositivos` separada: el bloqueo vive directamente en el usuario,
ya que en este alcance un gestor tiene un solo dispositivo autorizado a la
vez (no una flota de dispositivos por usuario).

### Comportamiento

`enrollment_service.validate()` (`backend/app/services/enrollment_service.py`):

1. Si el usuario **no** tiene un dispositivo bloqueado todavia, la primera
   validacion de QR con `device_fingerprint` lo bloquea (asset lock
   inicial).
2. Si el usuario **ya** tiene un dispositivo bloqueado y la validacion
   llega con un `device_fingerprint` distinto, se rechaza con
   `403 Forbidden` -- el codigo QR **no se consume** (`used_at` no se
   marca), asi que sigue disponible si el dispositivo correcto lo valida
   despues, o si un administrador libera el bloqueo primero.
3. Si el `device_fingerprint` coincide con el bloqueado, la validacion
   procede con normalidad (re-enrolamientos del mismo dispositivo).

### Liberar un dispositivo (reemplazo legitimo)

`POST /api/v1/enrollment/reset-device` (permiso `identity.users.manage`,
con acceso al proyecto del gestor) limpia
`locked_device_fingerprint`/`device_lock_updated_at`, permitiendo que el
siguiente QR validado desde un dispositivo nuevo tome el bloqueo. Cubre el
caso legitimo de "el gestor recibio una tablet nueva" sin reabrir la
puerta a un dispositivo robado que intente re-enrolarse por su cuenta.

## Sesion extendida para dispositivos de campo

### Config

`access_token_expire_minutes_field_device: int = 600` (10 horas,
`backend/app/core/config.py`), junto al ya existente
`access_token_expire_minutes: int = 60` para el resto de sesiones.

### Como se activa

`create_access_token()` (`backend/app/core/security.py`) ya aceptaba un
`expires_delta` opcional desde el modulo de credenciales de emergencia
(ver `docs/90_GOBERNANZA_SOPORTE_HELPDESK.md`). `LoginRequest` y
`MfaVerifyRequest` (`backend/app/schemas/auth.py`) ahora aceptan un
`device_fingerprint` opcional. `AuthService._field_device_expiry()`
(`backend/app/services/auth_service.py`) decide la expiracion real:

- Si el `device_fingerprint` enviado en el login **coincide** con
  `User.locked_device_fingerprint` (el dispositivo ya paso por el asset
  lock de enrolamiento QR), el token se emite con `expires_delta=600min`.
- En cualquier otro caso (sin `device_fingerprint`, dispositivo distinto,
  o usuario sin dispositivo bloqueado todavia), se usa la expiracion
  normal de 60 minutos -- **retrocompatible**: un login sin ese campo se
  comporta exactamente igual que antes de este cambio.

Aplica tanto al login directo (`POST /auth/login`) como al login con MFA
(`POST /auth/mfa/verify`), ya que ambos terminan en `create_access_token`.

## Pruebas

- `backend/tests/test_enrollment.py`:
  `test_device_lock_binds_on_first_enrollment_and_blocks_a_different_device`
  (bloqueo en el primer enrolamiento, rechazo desde otro dispositivo, el
  token rechazado sigue sirviendo si luego se usa el dispositivo correcto)
  y `test_admin_can_reset_device_lock_to_allow_a_new_device` (permiso
  requerido, liberacion exitosa habilita un dispositivo nuevo).
- `backend/tests/test_field_device_session.py`: login sin
  `device_fingerprint` o con uno distinto al bloqueado usa la expiracion
  default; login con el dispositivo correcto obtiene los ~600 minutos
  completos; el mismo comportamiento se confirma tambien en el flujo con
  MFA.

## Verificado con backend real

Contra el backend demo: se genero un QR y se valido desde
`device_fingerprint=tablet-real-001` (bloqueo inicial exitoso); un segundo
QR validado desde `stolen-device-999` fue rechazado con `403` y el mensaje
de bloqueo; un login posterior con `device_fingerprint=tablet-real-001`
devolvio un token con expiracion de **600.0 minutos exactos**, mientras que
un login sin ese campo devolvio **60.0 minutos** -- confirmando ambos
caminos con el token JWT real decodificado.

## Limites conocidos

- El asset lock es 1:1 (un dispositivo por usuario), no una flota de
  dispositivos autorizados por gestor.
- No hay pantalla propia en el frontend para `reset-device` todavia; se
  opera via Swagger/API, igual que otros endpoints administrativos antes
  de tener UI dedicada.
- La sesion extendida depende de que el frontend/PWA envie
  `device_fingerprint` en el login (ya genera y persiste uno en
  `localStorage` para el flujo de enrolamiento QR,
  `frontend/src/modules/enrollment/EnrollScanApp.tsx`); el formulario de
  login web actual todavia no lo reutiliza automaticamente para ese
  campo -- queda pendiente de UI, no de backend.
