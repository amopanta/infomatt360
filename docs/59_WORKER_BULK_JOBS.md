# Worker para jobs bulk

## Objetivo

Separar el procesamiento de cargas masivas del proceso web principal.

El API puede recibir lotes con:

```json
{
  "processing_mode": "queued"
}
```

Y un proceso aparte se encarga de procesarlos. Esto evita que una carga pesada
compita directamente con las solicitudes normales de usuarios.

## Comando

Desde `backend`:

```powershell
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --limit 50
```

Procesa hasta 50 jobs en estado `queued` y termina.

Cada job tomado se marca primero como:

```text
status=processing
worker_id=<identificador-del-worker>
locked_at=<fecha-hora>
attempt_count=attempt_count+1
```

Esto reduce el riesgo de que dos workers procesen el mismo lote.

## Modo continuo

```powershell
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --limit 50 --loop --sleep-seconds 5
```

Esto ejecuta ciclos continuos, esperando 5 segundos entre cada ciclo.

## Filtros opcionales

```powershell
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --project-id demo-project-infomatt360
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --template-id demo-template-characterization
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --worker-id worker-bulk-01
```

## Salida

El comando imprime JSON por ciclo:

```json
{
  "requested_limit": 50,
  "picked": 2,
  "processed": 2,
  "failed": 0,
  "processed_jobs": [],
  "failed_jobs": []
}
```

El mismo ciclo alimenta las metricas operativas disponibles en:

```text
GET /api/v1/health/metrics
```

Seccion:

```text
bulk_jobs
```

## Produccion

Para produccion, ejecutar este comando como servicio separado:

- Windows Task Scheduler o servicio Windows;
- systemd en Linux;
- contenedor worker aparte;
- job programado por Kubernetes/CronJob si se requiere por ventanas.

## Reintentos y fallos

Cada job conserva:

- `attempt_count`;
- `max_attempts`;
- `next_attempt_at`;
- `last_error`;
- `worker_id`;
- `locked_at`.

Si ocurre un error de procesamiento:

- si `attempt_count < max_attempts`, el job vuelve a `queued`;
- `next_attempt_at` define cuando puede volver a tomarse;
- si `attempt_count >= max_attempts`, queda en `failed`;
- `last_error` conserva el motivo operativo del fallo.

Configuracion del backoff:

```text
BULK_WORKER_RETRY_BACKOFF_SECONDS=60
BULK_WORKER_RETRY_MAX_BACKOFF_SECONDS=3600
BULK_WORKER_STALE_AFTER_SECONDS=1800
BULK_WORKER_HEARTBEAT_EVERY_RECORDS=100
```

La espera crece de forma exponencial:

```text
60s, 120s, 240s ... hasta el maximo configurado
```

## Recuperacion de jobs atascados

Si un worker se cae mientras procesa un job, el lote puede quedar en:

```text
status=processing
```

Al inicio de cada ciclo, el worker busca jobs `processing` cuyo `locked_at`
sea anterior a `BULK_WORKER_STALE_AFTER_SECONDS`.

Cuando encuentra uno:

- limpia `worker_id`;
- limpia `locked_at`;
- registra `last_error`;
- si aun tiene intentos disponibles, vuelve a `queued` con backoff;
- si ya agoto `max_attempts`, queda en `failed`.

Esto evita que un lote quede bloqueado indefinidamente por una caida del proceso.

## Heartbeat durante procesamiento

Mientras procesa un lote, el worker renueva `locked_at` al iniciar el trabajo
y luego cada `BULK_WORKER_HEARTBEAT_EVERY_RECORDS` registros completados.

Esto evita falsos positivos en lotes grandes: si un job tarda varios minutos
por volumen, el siguiente ciclo puede distinguir entre "worker vivo trabajando"
y "worker caido sin heartbeat".

## Siguiente evolucion

Este worker usa la tabla `bulk_import_jobs` como cola simple. Para cargas
masivas sostenidas se recomienda evolucionar a:

- Celery/RQ/arq;
- Redis/RabbitMQ como broker;
- reintentos con backoff mas politicas por tipo de error;
- bloqueo atomico por job con garantias fuertes para multiples workers concurrentes;
- metricas por job y alertas de fallos.
