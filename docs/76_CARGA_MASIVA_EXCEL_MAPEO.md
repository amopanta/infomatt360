# Carga masiva Excel con mapeo y aprobacion

## Objetivo

Importar participantes o usuarios desde un archivo `.xlsx` con columnas
arbitrarias, dejando que un administrador confirme el mapeo de columnas y
apruebe la importacion antes de que se creen los registros.

## Por que no reutiliza el worker de `bulk_import.py`

`BulkImportJob` (modulo previo) sincroniza respuestas de formulario **ya
estructuradas** enviadas por API/dispositivo. Este motor nuevo
(`backend/app/services/excel_import_service.py`) resuelve un problema
distinto: filas crudas de un Excel con encabezados que varian por cliente
("Documento", "Cedula", "Identificacion" pueden ser la misma columna). Por
eso usa su propio modelo (`ExcelImportJob`,
`backend/app/models/excel_import.py`) en vez de extender el worker bulk.

## Flujo (3 pasos)

1. **Subir y previsualizar** — `upload_and_preview()` lee el `.xlsx` con
   `openpyxl`, detecta encabezados, propone un mapeo automatico segun un
   diccionario de alias conocidos (`documento`/`cedula`/`identificacion` ->
   `document_id`, etc.) y guarda una vista previa (primeras 20 filas).
2. **Confirmar mapeo** — `confirm_mapping()` permite al administrador
   corregir a que campo destino apunta cada columna antes de importar.
3. **Aprobar e importar** — `approve_and_import()` valida campos
   obligatorios por fila, crea cada `Participant` o `User` real, y deja un
   `error_report_json` por fila que fallo (sin abortar el lote completo).

## Entidades soportadas

| `entity_type` | Campos destino | Campos obligatorios |
| --- | --- | --- |
| `participants` | `document_id`, `full_name`, `external_code`, `participant_type` | `full_name` |
| `users` | `document_id`, `full_name`, `email`, `phone` | `full_name`, `document_id`, `email` |

## Endpoints

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/api/v1/excel-import/upload` | `identity.users.manage` |
| `PATCH` | `/api/v1/excel-import/{job_id}/mapping` | `identity.users.manage` |
| `POST` | `/api/v1/excel-import/{job_id}/approve` | `identity.users.manage` |
| `GET` | `/api/v1/excel-import/{job_id}` | acceso al proyecto |
| `GET` | `/api/v1/excel-import/project/{project_id}` | acceso al proyecto |

## Limites conocidos

- Sin pantalla propia en el frontend todavia (se opera por Swagger/API
  directa); ver la nota de prioridades en la auditoria original.
- Un fallo por fila (ej. duplicado, campo invalido) no revierte el lote
  completo: las filas validas se importan y las invalidas quedan reportadas
  en `error_report_json` para corregir y reintentar.
