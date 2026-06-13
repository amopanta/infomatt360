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

## Estados iniciales

```text
draft
submitted
approved
rejected
archived
```

## Soporte para valores complejos

`field_value_json` permite guardar texto, numeros, listas, GPS, firmas, archivos, OCR y estructuras futuras sin cambiar el modelo.

Ejemplo GPS:

```json
{"lat": 6.25, "lng": -75.56, "accuracy": 5}
```

Ejemplo archivo:

```json
{"fileId": "abc123", "url": "/storage/file.pdf"}
```

## Pendientes

- pruebas de integracion Builder -> Runtime -> Guardar -> Consultar;
- auditoria automatica;
- permisos por proyecto en consultas Runtime;
- frontend Runtime Renderer;
- reportes basicos sobre runtime_records.
