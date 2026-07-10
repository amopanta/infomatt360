# Produccion: secretos y configuracion segura

## Objetivo

Evitar que InfoMatt360 llegue a produccion con valores de desarrollo.

## Plantilla

Usar como base:

```text
.env.production.example
```

Copiar sus valores al entorno real del servidor o a `backend\.env` del ambiente
productivo.

## Generar SECRET_KEY

```powershell
.\scripts\generate-secret.cmd
```

El valor generado debe copiarse en `SECRET_KEY`. No debe compartirse ni
versionarse.

## Validar configuracion productiva

```powershell
.\scripts\doctor-production.cmd -EnvFile backend\.env
```

El doctor productivo falla si encuentra valores de desarrollo, placeholders o
configuraciones inseguras. Tambien valida limites numericos, Redis cuando se
activa para rate limiting/throttling, cookies seguras, observabilidad minima,
cabeceras HTTP de seguridad y parametros del worker bulk.

Ademas, el backend ejecuta una validacion de arranque cuando
`ENVIRONMENT=production`. Si detecta configuracion critica insegura, la API no
arranca y devuelve un `RuntimeError` con los puntos a corregir.

## Reglas minimas

- `ENVIRONMENT=production`
- `DEBUG=false`
- `AUTO_CREATE_TABLES=false`; en produccion las tablas se gestionan con Alembic.
- En desarrollo, `AUTO_CREATE_TABLES=true` solo crea tablas si la base no tiene `alembic_version`.
- `DATABASE_URL` con PostgreSQL, no SQLite.
- Usar el driver configurado en dependencias: `postgresql+psycopg2://...`
- `DATABASE_URL` no debe conservar `CHANGE_ME`, `REPLACE` ni dominios `example.com`.
- Pool SQLAlchemy configurado:
  - `DB_POOL_SIZE`
  - `DB_MAX_OVERFLOW`
  - `DB_POOL_TIMEOUT_SECONDS`
  - `DB_POOL_RECYCLE_SECONDS`
- Si hay muchos workers o replicas, considerar PgBouncer delante de PostgreSQL.
- `SECRET_KEY` fuerte y aleatorio.
- `REFRESH_COOKIE_SECURE=true` y `REFRESH_COOKIE_SAMESITE=strict/lax`; si no,
  el backend bloquea el arranque productivo.
- `FRONTEND_URL` con HTTPS.
- `CORS_ALLOWED_ORIGINS` explicito, con HTTPS y sin comodin `*`.
  El backend bloquea el arranque productivo si `FRONTEND_URL` o algun origen
  CORS usa HTTP.
- SMTP configurado para recuperacion de contrasena.
- `SMTP_HOST` y `SMTP_PASSWORD` no deben conservar placeholders.
- `UPLOAD_DIRECTORY` persistente, respaldado, existente y escribible por el proceso backend.
  El backend bloquea el arranque productivo si esta ruta no esta operativa y
  `/api/v1/health/ready` devuelve `503 not_ready` si falla durante operacion.
- Rate limiting global activo:
  - `API_RATE_LIMIT_ENABLED=true`
  - `API_RATE_LIMIT_REQUESTS` ajustado al uso esperado.
  - `API_RATE_LIMIT_WINDOW_SECONDS` ajustado al uso esperado.
  - `API_RATE_LIMIT_BACKEND=redis` recomendado en produccion multiworker.
  - `REDIS_URL` configurado si se activa Redis.
  - `API_RATE_LIMIT_HIGH_VOLUME_REQUESTS` debe ser mayor o igual a `API_RATE_LIMIT_API_KEY_REQUESTS`.
- Throttling de autenticacion:
  - `AUTH_THROTTLE_BACKEND=db` para desarrollo/simple.
  - `AUTH_THROTTLE_BACKEND=redis` recomendado para login, MFA, refresh y recuperacion de contrasena bajo alta frecuencia.
  - Cuando Redis bloquea un identificador, se conserva un snapshot en `auth_throttles` para trazabilidad.
- Si hay reverse proxy, declarar sus IPs en `API_RATE_LIMIT_TRUSTED_PROXY_IPS`.
  - Si esta variable queda vacia, el backend ignora `X-Forwarded-For` y usa la IP real del socket.
  - Nunca confiar en `X-Forwarded-For` enviado directamente por el cliente.
- `API_KEY_PROFILE_CACHE_TTL_SECONDS` permite cachear brevemente el perfil de API key para reducir consultas repetidas a base de datos.
- Observabilidad minima:
  - `REQUEST_LOGGING_ENABLED=true`
  - `REQUEST_ID_HEADER=X-Request-ID`
  - cada respuesta incluye `X-Request-ID` para correlacionar frontend, API y logs.
  - `METRICS_ENABLED=true`
  - `/api/v1/health/metrics` expone contadores HTTP basicos por estado, ruta y latencia solo a usuarios autenticados con permisos operativos.
  - `/api/v1/health/metrics/prometheus` expone texto Prometheus protegido por los mismos permisos.
  - El menu administrativo y las rutas administrativas directas del frontend se filtran con los permisos del proyecto activo, pero los endpoints backend siguen validando permisos en cada llamada.
- Cabeceras de seguridad HTTP:
  - `SECURITY_HEADERS_ENABLED=true`
  - `X-Content-Type-Options=nosniff`
  - `X-Frame-Options=DENY`
  - `Referrer-Policy=no-referrer`
  - `Permissions-Policy` sin camara, microfono ni geolocalizacion por defecto.
  - `Content-Security-Policy` defensiva para respuestas del API.
- Gestion de API keys protegida con permiso `integrations.api_keys.manage`.
- API keys entregadas a integraciones externas por canal seguro; el secreto completo solo se muestra una vez.
- Worker bulk:
  - `BULK_WORKER_RETRY_BACKOFF_SECONDS`
  - `BULK_WORKER_RETRY_MAX_BACKOFF_SECONDS`
  - `BULK_WORKER_STALE_AFTER_SECONDS`
  - el backoff maximo debe ser mayor o igual al backoff inicial.

## Tokens web

El refresh token se entrega por cookie `httpOnly` para que JavaScript no pueda leerlo directamente ante un XSS. Configuracion requerida:

- `REFRESH_COOKIE_NAME`
- `REFRESH_COOKIE_SECURE=true` en produccion;
- `REFRESH_COOKIE_SAMESITE=strict` o `lax`;
- frontend usando `credentials: "include"` en login/MFA/refresh/logout.
- access token conservado solo en memoria del frontend; no se persiste en `localStorage`.
- `/auth/refresh` con cookie valida `Origin/Referer` contra `FRONTEND_URL` y `CORS_ALLOWED_ORIGINS` en produccion.

Pendientes recomendados antes de produccion real:

- complementar con CSP especifica del frontend cuando se sirva la SPA desde dominio productivo;
- revisar estrategia CSRF si se agregan endpoints autenticados solo por cookie.

## Indices de autorizacion

Las consultas frecuentes de permisos usan `user_project_assignments` por usuario, proyecto y estado. Para evitar table scans al crecer la tabla, existen indices compuestos:

```text
ix_assignments_user_project_status(user_id, project_id, status)
ix_assignments_project_status_role(project_id, status, role_id)
```
