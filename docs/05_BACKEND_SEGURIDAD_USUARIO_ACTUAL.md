# Backend - Seguridad y Usuario Actual

## Objetivo
Agregar una capa base para proteger endpoints con token JWT y consultar el usuario autenticado.

## Archivos agregados

```text
backend/app/api/deps.py
backend/app/api/v1/security.py
backend/app/schemas/security.py
```

## Endpoint protegido

```text
GET /api/v1/security/me
```

Este endpoint requiere token Bearer y devuelve:

- id de usuario;
- nombre;
- correo;
- estado;
- canales permitidos.

## Flujo

1. El usuario inicia sesion en `/api/v1/auth/login`.
2. El backend retorna un token JWT.
3. Web, Android o escritorio envian el token como Bearer.
4. El backend valida firma, expiracion y estado del usuario.
5. El endpoint puede usar el usuario actual.
6. `/api/v1/auth/session` devuelve solo proyectos activos asignados al usuario.
7. `/api/v1/auth/logout` revoca todas las sesiones activas del usuario.
8. El frontend rota el refresh token antes de vencer el JWT y al recuperar una sesion expirada.
9. El usuario puede activar MFA desde `/account/security`; si esta activo, el login exige TOTP o un codigo de recuperacion.

## Administracion segura de cuentas

El permiso `identity.users.manage` habilita, dentro del mismo proyecto:

```text
GET   /api/v1/security/admin/projects/{project_id}/users
PATCH /api/v1/security/admin/projects/{project_id}/users/{user_id}/email
POST  /api/v1/security/admin/projects/{project_id}/users/{user_id}/password-reset
POST  /api/v1/security/admin/projects/{project_id}/users/{user_id}/mfa-reset
```

Corregir el correo o reiniciar una clave exige que el administrador confirme su
propia contrasena. El reinicio puede generar una clave temporal segura o aceptar
una definida por el administrador, obliga al usuario a cambiarla al ingresar,
invalida sus sesiones anteriores y registra la operacion en auditoria sin guardar
la clave temporal.

Si una persona pierde su autenticador y sus codigos de recuperacion, el mismo
permiso permite reiniciar MFA. La operacion exige la contrasena del administrador,
revoca sesiones y queda registrada en auditoria.

Los intentos de autenticacion, recuperacion y uso de tokens invalidos tienen
ventanas de limitacion y bloqueo temporal. Sus claves de control se almacenan
como HMAC para no crear una segunda base de correos o direcciones IP legibles.

## Pendientes

- permisos por modulo;
- permisos por accion;
- rotacion de claves.
