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

## Pantalla en el frontend

`frontend/src/modules/admin/ExcelImportApp.tsx` (ruta
`/admin/excel-import`, permiso `identity.users.manage`): asistente de 3
pasos que sigue el mismo flujo del backend.

1. Selecciona tipo de entidad (participantes/usuarios) y archivo `.xlsx`,
   sube y previsualiza.
2. Muestra una tabla de mapeo -- una fila por columna del Excel, con un
   selector del campo destino (prellenado con la deteccion automatica del
   backend) y dos filas de ejemplo por columna para verificar visualmente
   antes de confirmar.
3. Tras confirmar el mapeo, el boton "Aprobar e importar" ejecuta la
   importacion real y muestra el conteo final de filas importadas/fallidas
   y el detalle de errores por fila si los hay.

Debajo, un historial de todos los lotes del proyecto (archivo, tipo,
estado, conteo). Cliente API en
`frontend/src/modules/admin/excelImportApi.ts` (usa `FormData` para la
subida, no JSON).

Verificado contra backend real: se creo un `.xlsx` de prueba con
`openpyxl` (2 filas, columnas `documento`/`nombre completo`/`codigo`), se
subio y confirmo el mapeo, se aprobo, y los 2 participantes aparecieron
consultables en `GET /participants/project/{id}` -- el flujo completo
subir->mapear->aprobar funciona de punta a punta. La seleccion de archivo
en si se probo contra el endpoint (no hay control de dialogo nativo de
archivos en el entorno de automatizacion del navegador usado para
verificar), pero es la misma llamada `multipart/form-data` que el boton
"Subir y previsualizar" del frontend invoca.

## Limites conocidos

- Un fallo por fila (ej. duplicado, campo invalido) no revierte el lote
  completo: las filas validas se importan y las invalidas quedan reportadas
  en `error_report_json` para corregir y reintentar.
