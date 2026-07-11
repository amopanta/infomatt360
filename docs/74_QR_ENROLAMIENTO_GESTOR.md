# QR de enrolamiento por gestor

## Objetivo

Permitir que un administrador enrole el dispositivo de un gestor (celular,
tablet) escaneando un codigo QR de un solo uso, en vez de compartir
credenciales por un canal inseguro.

## Modelo

`ManagerQrToken` (`backend/app/models/enrollment.py`): `project_id`,
`user_id` (el gestor a enrolar), `token_hash` (SHA-256 del token, nunca se
guarda en texto plano — mismo patron que `PasswordResetToken`),
`expires_at`, `used_at` (marca el token como consumido tras la primera
validacion exitosa), `device_fingerprint` (opcional, capturado en el
momento de validar).

## Endpoints

| Metodo | Ruta | Auth | Detalle |
| --- | --- | --- | --- |
| `POST` | `/api/v1/enrollment/qr` | `identity.users.manage` | Genera el PNG del QR y el token crudo (header `X-Enrollment-Token`) |
| `POST` | `/api/v1/enrollment/validate` | Ninguna (semi-publico) | Valida el token y lo marca usado |

`POST /enrollment/qr` valida ademas que el gestor (`payload.user_id`) tenga
acceso al proyecto (`404` si no) antes de emitir el codigo.

## Seguridad

- El token nunca se persiste en texto plano (solo su hash SHA-256).
- Un token solo se puede validar una vez (`used_at` se fija en la primera
  validacion exitosa; intentos posteriores devuelven `401`).
- `POST /enrollment/validate` es semi-publico por diseno (el dispositivo aun
  no tiene sesion), asi que tiene throttling por IP
  (`auth_throttle_service`, clave `qr-validate-ip`): bloquea 15 minutos tras
  10 intentos fallidos en una ventana de 15 minutos.
- Exponer el token crudo en el header `X-Enrollment-Token` de la respuesta
  de `/enrollment/qr` no agrega superficie de ataque: ese mismo token ya
  viaja codificado dentro de la imagen QR, que es lo que un dispositivo
  real escanearia.

## Frontend

- Generacion: boton "Generar QR de enrolamiento" en
  `frontend/src/modules/admin/AdminUserSecurityApp.tsx`, que descarga el PNG
  como blob URL (`generateEnrollmentQr()` en `admin/api.ts`).
- Escaneo: `frontend/src/modules/enrollment/EnrollScanApp.tsx`, ruta publica
  `/enroll` (registrada en `AuthGate.tsx`). Si la URL trae `?token=...` lo
  valida directo; si no, abre la camara (`getUserMedia`) y decodifica cada
  cuadro con `jsqr` hasta encontrar un QR valido.

## Limites conocidos

- El enrolamiento valida el token y confirma acceso al proyecto, pero no
  crea todavia una sesion autenticada por si solo: el dispositivo enrolado
  sigue necesitando iniciar sesion con las credenciales del gestor. El
  enrolamiento resuelve la distribucion segura del acceso inicial al
  proyecto, no reemplaza el login.
