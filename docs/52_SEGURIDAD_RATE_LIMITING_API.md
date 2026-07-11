# Seguridad - API Rate Limiting

## Objetivo

Reducir abuso de API, automatizaciones agresivas, scraping interno y ataques basicos de denegacion por exceso de solicitudes.

## Estado

Implementado como middleware global de FastAPI.

## Alcance

El limite aplica por:

```text
IP + metodo HTTP + ruta
```

Ejemplo:

```text
203.0.113.10:GET:/api/v1/auth/session
```

## Respuesta cuando se excede el limite

```http
429 Too Many Requests
Retry-After: <segundos>
X-RateLimit-Limit: <limite>
X-RateLimit-Remaining: 0
```

## Endpoints exentos

```text
/health
/api/v1/health/*
```

Esto evita bloquear balanceadores, health checks y monitoreo.

## Configuracion

Variables disponibles:

```text
API_RATE_LIMIT_ENABLED=true
API_RATE_LIMIT_REQUESTS=120
API_RATE_LIMIT_WINDOW_SECONDS=60
API_RATE_LIMIT_API_KEY_REQUESTS=10000
API_RATE_LIMIT_HIGH_VOLUME_REQUESTS=1000000
API_RATE_LIMIT_BACKEND=memory
REDIS_URL=
API_RATE_LIMIT_REDIS_PREFIX=infomatt360:rate-limit
```

## Perfiles para integraciones

Las API keys pueden usar perfiles de volumen:

```text
standard      -> limite amplio para integraciones normales
high_volume   -> limite alto para sincronizaciones grandes
trusted_sync  -> sin limite estricto del middleware global
```

Esto permite proteger la API para usuarios normales sin bloquear integraciones masivas o sincronizaciones confiables.

## Backend distribuido con Redis

Por defecto se usa memoria local del proceso. Es suficiente para MVP, demo local y despliegues pequenos de un solo proceso.

Para produccion multiworker o multiples servidores, activar Redis:

```text
API_RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://usuario:password@redis.example.com:6379/0
```

Si `API_RATE_LIMIT_BACKEND=redis` queda configurado pero `REDIS_URL` esta vacio, el sistema vuelve a memoria local para no romper arranques de desarrollo.

El endpoint `/api/v1/health/ready` valida Redis cuando `API_RATE_LIMIT_BACKEND=redis` o `AUTH_THROTTLE_BACKEND=redis`.
En desarrollo puede advertir sin bloquear, pero en produccion devuelve `503 not_ready` si Redis esta requerido y no esta configurado o no responde.

## Throttling de autenticacion

Login, MFA, refresh, recuperacion y reseteo de contrasena usan un throttling propio para no revelar si una cuenta existe y limitar ataques de fuerza bruta.

Configuracion:

```text
AUTH_THROTTLE_BACKEND=db
AUTH_THROTTLE_REDIS_PREFIX=infomatt360:auth-throttle
```

En produccion de alto volumen:

```text
AUTH_THROTTLE_BACKEND=redis
REDIS_URL=redis://usuario:password@redis.example.com:6379/0
```

Con Redis activo, el contador de intentos se resuelve en Redis y solo se guarda un snapshot en `auth_throttles` cuando un identificador queda bloqueado. Asi se reduce carga en base de datos sin perder trazabilidad operativa.

## Pruebas

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests\test_api_rate_limit.py -q
```
