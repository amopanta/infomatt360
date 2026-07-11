# Observabilidad y metricas operativas

## Objetivo

Dar una visibilidad inicial del comportamiento HTTP de InfoMatt360 sin obligar
a instalar Prometheus, OpenTelemetry o agentes externos desde el primer dia.

## Endpoint

```text
GET /api/v1/health/metrics
```

Requiere usuario autenticado con al menos un permiso operativo fuerte:
`identity.users.manage`, `integrations.api_keys.manage`, `records.approve` o
`records.write`. Los endpoints basicos `/health` y `/api/v1/health/ready`
pueden seguir usandose para balanceadores y monitoreo simple, pero las
metricas detalladas no quedan expuestas publicamente.

Salida compatible con Prometheus:

```text
GET /api/v1/health/metrics/prometheus
```

Devuelve `text/plain; version=0.0.4` con contadores HTTP, latencias globales,
latencias por ruta y metricas del worker bulk. Reutiliza la misma proteccion
por permisos operativos del endpoint JSON.

Tambien existe vista administrativa en:

```text
/admin/metrics
```

Esta pantalla muestra requests totales, uptime, promedio, maximo, p50, p95,
p99, conteos HTTP, alertas operativas y rutas con mas trafico o mayor latencia
p95.

El frontend usa los permisos del proyecto activo devueltos por `/auth/session`
para mostrar u ocultar la entrada administrativa de metricas y para bloquear
la ruta directa con una pantalla de acceso restringido. El backend sigue siendo
la barrera de seguridad final.

Entrega:

- tiempo activo del proceso;
- solicitudes totales;
- latencia promedio y maxima;
- latencia p50, p95 y p99 global;
- conteo por familia de estado: `2xx`, `4xx`, `5xx`;
- conteo por codigo exacto: `401`, `403`, `429`, `500`, etc.;
- alertas visuales para `5xx`, `429`, `401/403` y jobs bulk fallidos o reintentados;
- resumen por ruta con requests, latencia promedio, latencia maxima, p50/p95/p99 y ultimo codigo.
- metricas del worker bulk en la seccion `bulk_jobs`.

## Metricas bulk

La seccion `bulk_jobs` incluye:

- `worker_cycles`: ciclos ejecutados por el worker;
- `picked`: jobs tomados de la cola;
- `processed`: jobs procesados correctamente por ciclo;
- `failed`: jobs que fallaron durante el ciclo;
- `recovered_stale`: jobs atascados recuperados desde `processing`;
- `failed_stale`: jobs atascados marcados como `failed`;
- `retries_scheduled`: jobs reprogramados con backoff;
- `completed_jobs`: jobs completados;
- `failed_jobs`: jobs marcados como fallidos.

## Configuracion

```text
METRICS_ENABLED=true
REQUEST_LOGGING_ENABLED=true
REQUEST_ID_HEADER=X-Request-ID
```

Si `METRICS_ENABLED=false`, el endpoint sigue respondiendo pero los contadores
no se alimentan desde el middleware.

## Trazabilidad por request

El backend acepta `X-Request-ID` en CORS y tambien lo expone en la respuesta
HTTP. Esto permite que el frontend, una integracion externa o un proceso de
sincronizacion masiva envie su propio identificador de correlacion y lo pueda
leer de vuelta.

Recomendacion para integraciones:

- generar un `X-Request-ID` unico por lote, job o request;
- guardarlo en los logs del sistema externo;
- usar el mismo valor para buscar el evento en los logs de InfoMatt360;
- si el cliente no envia la cabecera, InfoMatt360 genera un UUID seguro.

## Alcance actual

Estas metricas son en memoria por proceso. Sirven para:

- demo;
- preproduccion;
- una instancia pequena;
- diagnostico rapido de aumento de `401`, `403`, `429` o `500`.

## Siguiente salto industrial

Para produccion con varias replicas:

- conectar `/api/v1/health/metrics/prometheus` a Prometheus/Grafana;
- ampliar hacia OpenTelemetry/tracing distribuido;
- graficar dashboards de latencia p50/p95/p99 desde `/api/v1/health/metrics`;
- alertas por aumento de `429`, `500` y errores de jobs bulk;
- alertas por `failed_jobs`, `failed_stale` y crecimiento de `retries_scheduled`;
- trazas por `X-Request-ID` cruzando frontend, API y workers.
