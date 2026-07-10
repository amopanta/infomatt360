# Auth web: refresh token en cookie httpOnly

## Objetivo

Reducir el impacto de XSS evitando que el refresh token quede legible desde JavaScript.

## Cambio aplicado

- `POST /auth/login` crea refresh token y lo entrega como cookie `httpOnly`.
- `POST /auth/mfa/verify` tambien entrega la cookie al completar MFA.
- `POST /auth/refresh` puede leer el refresh token desde la cookie.
- `POST /auth/logout` limpia la cookie.
- El body de login/MFA/refresh ya no necesita exponer `refresh_token` para el frontend nuevo.
- Se mantiene compatibilidad temporal: `/auth/refresh` aun acepta `refresh_token` en el body para clientes antiguos.

## Configuracion

```text
REFRESH_COOKIE_NAME=infomatt360_refresh
REFRESH_COOKIE_SECURE=true
REFRESH_COOKIE_SAMESITE=strict
```

En desarrollo local `REFRESH_COOKIE_SECURE=false` permite probar por HTTP.

## Frontend

Las llamadas de autenticacion usan:

```ts
credentials: "include"
```

Esto permite que el navegador guarde y envie la cookie sin exponer el valor a JavaScript.

El access token ya no se persiste en `localStorage`. Se conserva solo en memoria
del runtime frontend y se renueva con `POST /auth/refresh` usando la cookie
`httpOnly`. Si existe un token antiguo en `localStorage`, el frontend lo migra a
memoria y lo borra.

## Proteccion CSRF de refresh

En produccion, cuando `/auth/refresh` usa la cookie `httpOnly`, el backend valida
que el encabezado `Origin` o `Referer` corresponda a `FRONTEND_URL` o a algun
origen configurado en `CORS_ALLOWED_ORIGINS`.

Esto reduce el riesgo de llamadas cross-site no deseadas contra el refresh token
sin romper clientes legacy que todavia envian `refresh_token` en el body.

## Pendiente

Pendientes recomendados:

- reforzar CSP especifica del frontend cuando se sirva la SPA desde dominio productivo;
- revisar estrategia CSRF si se agregan nuevos endpoints autenticados solo por cookie;
- evaluar rotacion aun mas corta del access token segun riesgo operativo.
