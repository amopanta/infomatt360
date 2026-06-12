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

## Pendientes

- permisos por proyecto;
- permisos por modulo;
- permisos por accion;
- refresh token;
- cierre de sesion;
- bloqueo por intentos fallidos;
- rotacion de claves.
