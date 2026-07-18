# 112. Descarga masiva de evidencias en ZIP

## Qué cierra esto

El ítem #7 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md`: "Descarga masiva de evidencias en ZIP filtrada por participante/formulario/proyecto/fecha/estado/gestor, con renombrado automático (§18)". Antes de este cambio, `file_service.py`/`files.py` solo manejaban subida y listado individual de evidencias — **no existía ninguna capacidad de descarga/lectura de bytes**, ni individual ni en lote, ni en disco local ni en S3.

**Decisiones de alcance acordadas con el usuario:** el requerimiento pide un filtro "gestor" que no tiene campo dedicado en el modelo de datos (no existe concepto de "gestor asignado" en ningún lado). Se mapeó a `FileAsset.created_by` (quien subió el archivo) — opción recomendada, elegida explícitamente sobre `RuntimeRecord.submitted_by` o sobre omitir el filtro. El esquema de renombrado automático elegido fue `Participante_TipoEvidencia_Fecha` (p.ej. `Ana-Gomez_IMAGE_2026-07-18.jpg`), también la opción recomendada.

## Diseño

### Sin modelo ni migración nueva

Cada campo de filtro que pide el requerimiento resuelve contra columnas existentes de `FileAsset` o un join hacia `RuntimeRecord`: `participant_id`/`created_by` (gestor) ya están en `FileAsset`; fecha usa `FileAsset.created_at`; "formulario" (template) y "estado" no existen en `FileAsset` pero sí en `RuntimeRecord` (`template_id`, `status`), alcanzables vía `FileAsset.record_id → RuntimeRecord.id`. Es un `INNER JOIN`: un archivo sin `record_id` nunca calza con el filtro de formulario o estado, comportamiento correcto, no un caso a corregir. Este es un feature de filtro+exportación puro, sin nuevo estado persistido.

### Lectura de bytes, construida desde cero

`file_service.py` solo tenía operaciones de escritura (`upload`/`upload_local`/`upload_s3`). Se agregaron `read_local` (lectura directa de disco con verificación de existencia) y `read_asset_bytes` (despacha a local o S3 según `storage_provider`). Para S3, `s3_storage_service.py` (que antes solo tenía `upload_file`) ganó `get_object`, reutilizando el mismo `_client(profile)` que ya arma el cliente boto3 para subir.

El perfil S3 para leer se resuelve por el **bucket embebido en `storage_path`** (`s3://{bucket}/{key}`), no por el perfil default actual del proyecto: el default puede haber rotado (nuevas credenciales/bucket) después de que un archivo ya se escribió con el perfil anterior, y usar el default arriesgaría leer con credenciales equivocadas.

### ZIP en lote: mismo patrón que la generación masiva de actas (docs/110)

`file_service.download_batch` construye el ZIP en memoria (`io.BytesIO()` + `zipfile.ZipFile`), con un `try`/`except` por ítem para que un fallo individual no aborte el lote — se anota en `manifest.csv` (mismo formato UTF-8 BOM + `csv.writer` que `acta_service._manifest_csv`, duplicado localmente siguiendo la convención ya establecida de no compartir este helper entre servicios, igual que el sanitizador de nombres de archivo se duplica en `acta.py`/`reports.py`/`runtime.py`/`xlsform.py`). El renombrado (`evidence_naming.py::build_evidence_filename`) sigue el patrón `Participante_TipoEvidencia_Fecha`; colisiones (mismo participante+tipo+fecha, o coincidencia de nombre) se resuelven con sufijo `_2`, `_3`... vía un set de nombres usados — mismo patrón que `_slugify` en `multi_format_import_service.py`.

### Tope doble: cantidad de archivos y peso acumulado

El precedente de actas (`acta_batch_max_records=200`) es un tope solo de cantidad porque los PDFs generados son pequeños. Las evidencias pueden pesar hasta 25MB cada una (`settings.default_max_file_size_mb`, con override por `StorageProfile`) e incluir audio/video/imagen — reusar 200 sin cambios arriesgaría intentar bufferear varios GB en memoria dentro de una request sincrónica. Se agregaron dos settings nuevos: `evidence_batch_max_records = 100` y `evidence_batch_max_total_size_mb = 300`. El tope de peso se calcula con un `SUM(FileAsset.size_bytes)` sobre los ids resueltos (consulta barata, sin I/O) *antes* de abrir el ZIP; ambos topes devuelven `422` con el valor calculado en el mensaje, mismo patrón que el 422 de actas.

### Permiso: solo acceso al proyecto

Las rutas existentes de `files.py` (`POST /upload`, `GET /project/{id}`) solo verifican `assignment_service.user_has_project_access(...)` — no hay un permiso más estricto para evidencias como sí existe para editar plantillas de actas/formularios (`builder.write`). Descargar en lote lo que ya se puede listar y descargar uno por uno no es una escalada de privilegio, así que las rutas nuevas (`GET /{id}/download`, `POST /project/{id}/download-batch`, `GET /project/{id}/uploaders`) siguen el mismo criterio.

### Fuente de datos para el filtro "gestor"

`GET /assignments/?project_id=` está protegido por `identity.users.manage`, más restrictivo que "acceso al proyecto" — no servía para poblar un simple filtro. Se agregó `GET /files/project/{id}/uploaders`, de solo lectura, que revela únicamente quién efectivamente subió evidencias en ese proyecto (subconjunto de información que ya es visible en el propio listado de evidencias).

### `FileAssetRead` ganó `created_at`

El schema de lectura no exponía `created_at` (solo lo tiene el modelo). Se agregó porque la nueva galería de evidencias necesita mostrar la fecha de cada archivo — extensión mínima y directa, no una nueva capacidad.

### Frontend: módulo nuevo, greenfield

No existía ninguna pantalla de evidencias — lo único relacionado era el `<input type="file">` de subida en `RuntimeField.tsx`, que no cambió. `frontend/src/modules/evidence/EvidenceApp.tsx` agrega una pantalla nueva ("Evidencias" en el menú, ruta `/evidence`, sin restricción de permiso) con: filtros por participante/formulario/estado/gestor/rango de fechas, tabla con selección por checkbox, y un botón "Descargar ZIP" que usa la selección explícita si hay checkboxes marcados, o los filtros activos si no — mismo modo dual que el backend (`asset_ids` tiene prioridad, nunca se combinan ambos caminos, igual que `ActaRenderBatchRequest`/`buildBatchPayload` en docs/110). El botón "Descargar" por fila usa el nuevo endpoint individual. Los gráficos de barra/torta de reportes no aplican aquí; la UI reutiliza el vocabulario visual ya existente (`.records-table`, patrón de blob-download de `acta/api.ts`).

## Pruebas

`backend/tests/test_evidence_download.py` (12 pruebas nuevas, siguiendo el estilo de fixtures sembradas de `test_report_board.py` y el mock de S3 hecho a mano de `test_s3_storage.py`, sin `moto`): filtro combinado por participante/formulario/estado/gestor/fecha (incluyendo la exclusión de un archivo sin `record_id` por los filtros de formulario/estado); permiso 403 sin acceso al proyecto; `asset_ids` explícito con prioridad sobre filtros; ZIP con nombres renombrados y `manifest.csv`; colisión de nombre con sufijo `_2`; tope de cantidad → 422; tope de peso → 422; archivo local faltante en disco → falla ese ítem sin abortar el lote; descarga individual local; descarga vía S3 mockeado; fallo de S3 (`get_object`) → falla ese ítem sin abortar el lote; listado de gestores acotado al proyecto y protegido por acceso.

`frontend/src/modules/evidence/api.test.ts` (4 pruebas): `buildEvidenceBatchPayload` — ids explícitos vs. filtros, prioridad de ids sobre filtros, expansión de fecha a inicio/fin de día, filtros vacíos → `null`.

Suite completa tras el cambio: backend 399/399 (387 previos + 12 nuevos, mismos 5 errores preexistentes ya documentados — bloqueo de directorio temporal de Windows, no relacionado con este cambio), frontend 85/85 (81 previos + 4 nuevos), `tsc --noEmit` y `npm run build` limpios.

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`), sin necesidad de migración (no se agregó ninguna tabla):

- `/evidence` renderizó correctamente con las 2 evidencias reales del proyecto (`tiny.png`, subida real; `foto-demo.jpg`, fila de datos semilla sin archivo físico en disco), con los desplegables de participante/formulario/estado/gestor poblados con datos reales.
- Filtrar por gestor "Administrador Demo" redujo correctamente la tabla a solo `tiny.png`.
- La descarga individual (`GET /{id}/download`) de `tiny.png` devolvió `200`, `image/png`, y los 69 bytes exactos del archivo.
- La descarga en lote sin filtro activo devolvió `200` con un ZIP conteniendo `Sin-Participante_IMAGE_2026-07-11.png` (renombrado correcto) y `manifest.csv` — se confirmó, invocando `download_batch` directo contra la base de datos demo, que `foto-demo.jpg` (fila semilla sin archivo real en disco, preexistente y no creada por este cambio) queda correctamente marcada `failed` con el mensaje "El archivo no existe en el almacenamiento local" en el manifest, mientras `tiny.png` se incluye como `success` — confirma la resiliencia a fallos parciales funcionando exactamente como está diseñada, con datos reales imperfectos de la demo.
- Se marcó el checkbox de `tiny.png` y el botón cambió a "Descargar ZIP (1 seleccionadas)", confirmando que la selección explícita tiene prioridad sobre el filtro activo en la UI.
- No se creó ningún dato de prueba nuevo durante esta verificación (feature de solo lectura/exportación sobre datos existentes), por lo que no hubo necesidad de limpieza de base de datos.
- Se revirtieron `backend/.env` (línea `CORS_ALLOWED_ORIGINS` restaurada) y se eliminó `frontend/.env.local`.

## Lo que queda fuera de esta sesión

Con esto se cierran los 7 primeros ítems de docs/96 (#1-#7). Quedan #8 (GIS real con PostGIS), #9 (conectores BI nombrados), #10 (impresión nativa masiva de escritorio) y #11 (bandeja de correo externa vía IMAP).
