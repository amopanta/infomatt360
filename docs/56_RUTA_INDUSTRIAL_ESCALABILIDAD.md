# Ruta industrial de escalabilidad

## Estado actual reforzado

- Rate limiting ya no confia en `X-Forwarded-For` crudo.
- `X-Forwarded-For` solo se usa si el socket viene de una IP configurada en `API_RATE_LIMIT_TRUSTED_PROXY_IPS`.
- El perfil de API key se cachea con TTL corto para evitar consulta a base de datos en cada request.
- Cuando el perfil de API key no esta en cache, la consulta sincrona a base de datos se ejecuta en threadpool para no bloquear directamente el event loop del middleware.
- El arranque falla si `ENVIRONMENT=production` conserva configuracion insegura.
- PostgreSQL debe usarse con pool explicito.
- Las autorizaciones frecuentes tienen indices compuestos en `user_project_assignments`.
- Cada request recibe `X-Request-ID` y emite un log JSON basico con metodo, ruta, estado, duracion y cliente.
- Las respuestas del API incluyen cabeceras de seguridad: `nosniff`, anti-clickjacking, politica de referrer, permisos del navegador y CSP basica.
- El rate limiter ya tiene backend Redis opcional para despliegues multiworker o multiples replicas, con fallback a memoria cuando Redis no esta configurado.
- El throttling de autenticacion ya puede usar Redis como contador rapido, conservando snapshot en base de datos cuando se activa un bloqueo.
- El readiness `/api/v1/health/ready` ya valida Redis cuando es requerido por rate limiting o throttling y puede devolver `503 not_ready` en produccion si la dependencia falta.
- Existe endpoint de metricas operativas `/api/v1/health/metrics` protegido por permisos operativos, con latencia y conteo por codigos HTTP.
- Los lotes bulk `queued` ya pueden procesarse con un worker CLI separado del proceso web, con `worker_id`, `locked_at`, `attempt_count`, `max_attempts`, `next_attempt_at`, `last_error`, backoff exponencial y recuperacion de jobs `processing` atascados.
- `/api/v1/health/metrics` tambien expone metricas de jobs bulk: procesados, fallidos, recuperados, reintentados y atascados.
- `/api/v1/health/metrics/prometheus` expone metricas principales en formato Prometheus para integracion con Grafana/monitoreo externo.

## Siguiente salto recomendado

### 1. SQLAlchemy async

La arquitectura actual usa `Session` sincrono. Para throughput mayor:

- migrar gradualmente a `AsyncSession`;
- usar `asyncpg`;
- evitar consultas sincronas restantes dentro de endpoints `async def`;
- medir antes/despues con carga concurrente.

### 2. Workers/colas avanzadas

El worker bulk inicial ya permite separar cargas pesadas del API web y reduce duplicados reclamando jobs antes de procesarlos. Para operacion con multiples workers concurrentes de alto volumen:

- API web: atender requests;
- worker: procesar colas con bloqueo atomico fuerte por job;
- scheduler: disparar tareas;
- Redis/RabbitMQ/PostgreSQL queue segun estrategia.

### 3. Observabilidad avanzada

Pendiente para operacion industrial:

- ampliar metricas Prometheus y agregar OpenTelemetry/tracing distribuido;
- latencia p50/p95/p99 por endpoint;
- dashboard de errores;
- trazas de trabajos bulk y ETL.
