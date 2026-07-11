# API Bulk para sincronizacion masiva

## Objetivo

Reducir millones de solicitudes unitarias a cargas por lotes, sin quitar seguridad ni hacer dificil la integracion.

## Endpoint

```text
POST /api/v1/runtime/bulk/save
```

Autenticacion:

```http
X-API-Key: im360_<key_id>_<secret>
```

Permiso requerido en la API key:

```text
records.write
```

Perfil recomendado para grandes sincronizaciones:

```text
high_volume
trusted_sync
```

## Tamano del lote

La primera version permite hasta 10.000 registros por solicitud.

Para un escenario de 12 millones de registros cada 4 horas, eso permite bajar de 12 millones de llamadas unitarias a aproximadamente 1.200 llamadas bulk si se usan lotes de 10.000.

## Ejemplo

```json
{
  "project_id": "demo-project-infomatt360",
  "template_id": "demo-template-characterization",
  "idempotency_key": "sync-2026-06-25-0001",
  "processing_mode": "immediate",
  "continue_on_error": true,
  "records": [
    {
      "project_id": "demo-project-infomatt360",
      "template_id": "demo-template-characterization",
      "device_id": "sync-001",
      "values": [
        { "field_name": "nombre", "field_value_json": "\"Ana\"" },
        { "field_name": "edad", "field_value_json": "34" }
      ]
    }
  ]
}
```

## Respuesta

```json
{
  "project_id": "demo-project-infomatt360",
  "template_id": "demo-template-characterization",
  "job_id": "bulk-job-id",
  "idempotency_key": "sync-2026-06-25-0001",
  "job_status": "completed",
  "processing_mode": "immediate",
  "replayed": false,
  "received": 1,
  "created": 1,
  "failed": 0,
  "results": [
    { "index": 0, "id": "record-id", "status": "created", "error": null }
  ]
}
```

## Manejo de errores

Con `continue_on_error=true`, un registro fallido no detiene todo el lote. La respuesta indica el indice y error del item fallido.

Con `continue_on_error=false`, el procesamiento se detiene en el primer error.

## Idempotencia

Usar `idempotency_key` para cada lote enviado.

Si la integracion reintenta el mismo lote con la misma clave, el backend devuelve la respuesta guardada con:

```json
{ "replayed": true }
```

No se crean registros duplicados.

Si se reutiliza la misma `idempotency_key` con un payload diferente, el backend responde:

```http
409 Conflict
```

Recomendacion para generar claves:

```text
<sistema-origen>-<fecha>-<numero-lote>
```

Ejemplo:

```text
erp-20260625-000001
```

## Seguimiento de lotes

Cada lote idempotente devuelve un `job_id`. Ese identificador permite consultar el resultado posteriormente sin volver a enviar el payload completo.

Consultar un lote:

```text
GET /api/v1/runtime/bulk/jobs/{job_id}
```

Listar lotes recientes del proyecto asociado a la API key:

```text
GET /api/v1/runtime/bulk/jobs?template_id=demo-template-characterization&limit=25&offset=0
```

Ambos endpoints usan la misma autenticacion:

```http
X-API-Key: im360_<key_id>_<secret>
```

Esto permite a una integracion externa registrar: lote enviado, lote procesado, registros creados, registros fallidos y respuesta exacta del procesamiento.

Tambien existe panel administrativo para usuarios con permisos:

```text
/admin/bulk-jobs
```

## Procesamiento en cola

Para cargas grandes donde no se quiere dejar abierta la conexion esperando todo el procesamiento, enviar:

```json
{
  "project_id": "demo-project-infomatt360",
  "template_id": "demo-template-characterization",
  "idempotency_key": "sync-2026-06-25-0002",
  "processing_mode": "queued",
  "records": [
    {
      "project_id": "demo-project-infomatt360",
      "template_id": "demo-template-characterization",
      "values": [
        { "field_name": "nombre", "field_value_json": "\"Ana\"" }
      ]
    }
  ]
}
```

La respuesta queda en estado:

```json
{
  "job_id": "bulk-job-id",
  "job_status": "queued",
  "created": 0,
  "failed": 0
}
```

Luego el lote se procesa con:

```text
POST /api/v1/runtime/bulk/jobs/{job_id}/process
```

Si se llama de nuevo al mismo procesamiento cuando el lote ya esta `completed`, el sistema devuelve el resultado guardado y no duplica registros.

Tambien puede procesarse fuera del API web con el worker:

```powershell
cd backend
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --limit 50
```

Para dejarlo corriendo:

```powershell
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --limit 50 --loop --sleep-seconds 5
```

El worker marca cada job con `worker_id`, `locked_at`, `attempt_count` y `next_attempt_at`. Si un job falla, se reintenta con backoff exponencial hasta `max_attempts`; luego queda `failed` con `last_error`.

Si un worker cae y deja un lote en `processing`, el siguiente ciclo detecta el bloqueo vencido con `BULK_WORKER_STALE_AFTER_SECONDS` y lo devuelve a `queued` o lo marca `failed` si ya agoto intentos.

## Nota de performance

Esta primera version prioriza compatibilidad y seguridad. Para produccion con cargas masivas sostenidas se recomienda evolucionar a:

- inserciones bulk optimizadas por motor de base de datos;
- worker/cola de procesamiento asincrona real con Redis/RabbitMQ cuando haya varias replicas;
- idempotency keys por lote;
- compresion HTTP;
- particionamiento por proyecto/fecha.
