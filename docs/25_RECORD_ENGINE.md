# Record Engine - Persistencia Runtime

## Objetivo
Cerrar el flujo MVP de InfoMatt360 permitiendo guardar y consultar respuestas capturadas desde formularios Runtime.

## Decision tecnica
No se crean tablas por formulario. Se usa una estructura flexible:

```text
runtime_records
runtime_record_values
```

Esto permite soportar miles de formularios, versionado historico, Android offline, Desktop, IA, ETL y Base Espejo sin migraciones por cada formulario.

## Archivos agregados

```text
backend/app/models/runtime_record.py
backend/app/schemas/runtime_record.py
backend/app/services/runtime_record_service.py
backend/alembic/versions/0022_runtime_records.py
```

## Archivo actualizado

```text
backend/app/api/v1/runtime.py
```

## Endpoints

```text
POST /api/v1/runtime/save
GET /api/v1/runtime/record/{record_id}
GET /api/v1/runtime/template/{template_id}/records
GET /api/v1/runtime/template/{template_id}/records/search?search=&status=&limit=25&offset=0
GET /api/v1/runtime/template/{template_id}/records/export.csv?search=&status=
GET /api/v1/runtime/template/{template_id}/records/clean-export.csv?status=approved&date_from=&date_to=
GET /api/v1/runtime/template/{template_id}/records/observations.csv
PATCH /api/v1/runtime/record/{record_id}/correction
```

## Flujo

```text
Runtime JSON
  -> Captura usuario
  -> POST /runtime/save
  -> runtime_records
  -> runtime_record_values
  -> GET /runtime/record/{id}
```

## Estados

Actualizado 2026-10-18. Los iniciales eran `draft`, `submitted`, `approved`,
`rejected` y `archived`; hoy las transiciones por defecto
(`DEFAULT_ACTIONS` en `backend/app/services/approval_flow_service.py`, o el
flujo configurado del proyecto, docs/51) usan:

```text
draft -> submitted -> under_review -> tech_approved / coordinator_approved -> approved
                   \-> returned -> corrected -> (revision de nuevo)
rejected, archived, cancelled, voided (docs/100), synced
```

Solo se editan `draft` y, por su destinatario, `returned`/`corrected`
(docs/141 §4, `correction_service.ensure_can_edit`). Enviado, en revisión y
aprobado son de solo lectura.

## Soporte para valores complejos

`field_value_json` permite guardar texto, numeros, listas, GPS, firmas, archivos, OCR y estructuras futuras sin cambiar el modelo.

Antes de persistir, el API valida que cada valor sea JSON correcto y que no
existan nombres de campo duplicados. La cabecera y todos sus valores se guardan
en una sola transaccion; cualquier fallo revierte el registro completo.

Ejemplo GPS:

```json
{"lat": 6.25, "lng": -75.56, "accuracy": 5}
```

Ejemplo archivo:

```json
{"fileId": "abc123", "url": "/storage/file.pdf"}
```

## Consulta y exportacion

Las consultas Runtime validan la asignacion activa del usuario al proyecto. La
ruta `/records` ofrece busqueda, filtro por estado, detalle web y paginacion
desde servidor. El endpoint paginado devuelve:

```text
items: registros de la pagina
total: total filtrado
limit: tamano de pagina
offset: desplazamiento actual
```

La exportacion CSV acepta los mismos filtros `search` y `status`, genera UTF-8
compatible con Excel y protege columnas/celdas contra formulas inyectadas.

Para informes hay dos salidas separadas (docs/141 §8):
`clean-export.csv` (una fila por registro, sin observaciones, **solo
aprobados por defecto**; `status=todos` los incluye todos) y
`observations.csv` (las observaciones de revision).

## Pendientes

- auditoria automatica;
- exportacion XLSX nativa y trabajos asincronos para archivos grandes.
