# Panel administrativo de sincronizacion bulk

## Objetivo

Permitir que un administrador del proyecto supervise cargas masivas sin usar herramientas tecnicas externas.

## Ruta frontend

```text
/admin/bulk-jobs
```

Menu:

```text
Sincronizacion
```

## Capacidades

- listar lotes recibidos por API;
- ver resumen visual de lotes, pendientes, completados, fallidos, registros recibidos, creados, fallidos y tasa de exito;
- filtrar por estado y por `template_id`;
- ver estado del lote: `queued`, `processing`, `completed`, `failed`;
- ver conteos de registros recibidos, creados y fallidos;
- ver metricas operativas del worker: ciclos, tomados, procesados, fallos, recuperados, reintentos y atascados;
- ver estado operativo rapido: workers activos, lotes en procesamiento, reintentos pendientes y posibles atascados sin heartbeat reciente;
- ver alertas visuales cuando hay jobs fallidos, atascados fallidos o reintentos programados;
- consultar worker, heartbeat, intentos, proximo intento y ultimo error de cada lote;
- consultar detalle del resultado item por item;
- exportar errores del lote a CSV;
- procesar manualmente un lote en estado `queued`;
- permitir que un worker separado procese lotes `queued` sin usar el panel;
- evitar duplicados si se intenta procesar nuevamente un lote ya completado.

## Seguridad

El panel usa sesion de usuario, no requiere pegar el secreto de una API key en pantalla.

Permisos aceptados:

```text
integrations.api_keys.manage
records.write
```

## Endpoints administrativos

```text
GET /api/v1/runtime/bulk/admin/{project_id}/jobs
GET /api/v1/runtime/bulk/admin/{project_id}/summary
GET /api/v1/runtime/bulk/admin/{project_id}/jobs/{job_id}
POST /api/v1/runtime/bulk/admin/{project_id}/jobs/{job_id}/process
GET /api/v1/runtime/bulk/admin/{project_id}/jobs/{job_id}/errors.csv
```

Estos endpoints validan que el usuario tenga permiso sobre el proyecto antes de exponer informacion de lotes.

Filtros disponibles al listar:

```text
?status=queued&template_id=demo-template-characterization
```

## Uso recomendado

Para integraciones de alto volumen:

1. la integracion envia el lote con `processing_mode=queued`;
2. el sistema devuelve `job_id`;
3. el administrador puede ver el lote en el panel;
4. si hace falta, puede iniciar el procesamiento desde la interfaz o dejarlo al worker;
5. la integracion tambien puede consultar el resultado por API.

Worker recomendado:

```powershell
cd backend
.venv\Scripts\python.exe -m app.cli.process_bulk_jobs --limit 50 --loop --sleep-seconds 5
```
