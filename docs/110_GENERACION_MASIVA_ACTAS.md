# 110. Generación masiva de actas

## Qué cierra esto

El ítem #5 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md`: "Generación masiva de actas PDF (no solo una por una)".

**Alcance acordado con el usuario:** el usuario pidió inicialmente algo más grande ("plantillas personalizables tipo SQL Report, por íconos y variables") — se le mostró que eso ya lo resuelve el constructor visual de docs/109 (los bloques logo/encabezado/tabla/firma son los "íconos"; los selectores de campo y el helper de tokens son las "variables"), y se acordó que #5 solo agrega la parte que faltaba: aplicar una plantilla ya diseñada a **muchos registros a la vez**, con dos formas de elegirlos (filtro o selección manual) y entrega en un solo **ZIP**.

## Diseño

**Síncrono, sin cola de trabajos.** Todo precedente de descarga masiva de este repo (exportación CSV, exportación XLSX de reportes) es síncrono y completamente en memoria, un solo request/response — este endpoint sigue el mismo patrón. `BulkImportJob` (la cola asíncrona ya existente, usada para importación masiva por Excel) está diseñada para payloads JSON por fila, no para artefactos binarios; reusarla habría significado agregarle un concepto de "archivo resultado" que hoy no existe, una extensión real y no una reutilización directa. Un lote de actas es "decenas a cientos de documentos", el mismo orden de magnitud que ya maneja el resto del sistema de forma síncrona.

**Nuevo endpoint** `POST /acta-templates/{id}/render-batch` (`backend/app/api/v1/acta.py`), payload `ActaRenderBatchRequest{record_ids, search, status, unlinked_only}`: si vienen `record_ids` explícitos (selección manual) se usan tal cual; si no, se resuelven del lado del servidor con el mismo filtro que ya usa la pantalla de Registros, sin paginar (`runtime_record_service.list_filtered_record_ids`, nuevo método que reusa `_filtered_records_query` — la misma consulta interna que ya usa la exportación CSV — sin tocarla). Mismo permiso que el render de un solo registro (`user_has_project_access`, no `builder.write`): generar documentos de registros que ya se pueden ver no es una acción de diseño.

**Tope de 200 registros por lote**, configurable (`Settings.acta_batch_max_records`), con 422 explícito si se excede — no truncamiento silencioso. Genera un `HTTPException` con el límite en el mensaje.

**Un registro que falla no aborta el lote.** `acta_service.render_pdf_batch` reusa `render_pdf_from_record` sin cambios; si un registro no existe o pertenece a otro formulario, se anota en `manifest.csv` (dentro del mismo ZIP) como `failed` con el motivo, y el lote sigue — mismo espíritu "por ítem" que ya usa el guardado masivo de registros. El manifiesto va dentro del ZIP (no en un header de respuesta) porque el CORS de este backend solo expone `X-Request-ID` hoy, y cambiar eso para una sola función sería un cambio global innecesario.

**Frontend**: `RecordTable` (`frontend/src/modules/records/RecordsApp.tsx`) gana una columna de checkbox por fila, un "seleccionar todos los de esta página", y un botón "Seleccionar todos los que coinciden con el filtro (N)" junto a la paginación — mutuamente excluyente con la selección manual (activar uno apaga el otro). La selección manual **no se limpia** al cambiar de página o filtro (solo "Limpiar selección" la reinicia), a propósito: el punto de la selección manual es poder ir armando una lista curada entre páginas. Cuando hay algo seleccionado aparece `BulkActaBar`, que reusa la misma consulta de plantillas que ya usa `GenerateActaPanel` (filtradas al formulario actual) y llama `renderActaBatch` (mismo patrón de descarga por blob que `renderActaFromRecord`, pero con un ZIP en vez de un PDF).

## Pruebas

`backend/tests/test_acta.py` (8 pruebas nuevas): camino feliz con `record_ids` explícitos (ZIP con un PDF por registro + manifest, contenido real verificado con `pypdf`); camino feliz por filtro (`status`), confirmando que solo entran los registros que coinciden; falla parcial por registro de otro formulario; falla parcial por id inexistente; selección vacía → 422; tope excedido → 422 con el límite en el mensaje; plantilla legado rechazada; un usuario sin `builder.write` (solo acceso al proyecto) puede generar el lote igual.

`backend/tests/test_runtime_records.py` (1 prueba nueva): `list_filtered_record_ids` resuelve exactamente los registros que coinciden con el filtro sin paginar, verificado directamente contra el servicio.

`frontend/src/modules/records/selection.ts` (nuevo, 9 pruebas): `toggleSelection`, `selectPage`, `deselectPage`, `isPageFullySelected` — lógica pura de selección, extraída de `RecordTable` siguiendo el mismo patrón que `blockOrder.ts` (docs/109), ya que este repo no usa React Testing Library.

`frontend/src/modules/acta/api.test.ts` (4 pruebas nuevas): `buildBatchPayload` (extraída de `renderActaBatch` para poder probar la construcción del cuerpo del request sin mockear `fetch`, mismo patrón que `frontend/src/modules/enrollment/api.test.ts`).

Suite completa tras el cambio: backend 380/380 (371 previos + 9 nuevos, mismos 5 errores preexistentes documentados por el bloqueo de `.pytest_cache` en Windows), frontend 69/69 (56 previos + 13 nuevas), `tsc --noEmit` y `npm run build` limpios.

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`, formulario `demo-template-characterization`, 3 registros con estados `submitted/approved/submitted`):

- Se creó una plantilla de acta nueva vía `/acta` (la demo no tenía ninguna persistida).
- **Selección manual**: se marcaron 2 de los 3 registros por checkbox, apareció la barra "2 registro(s) seleccionado(s)", se generó el lote — `POST .../render-batch` real, 200 OK, mensaje "Lote de actas generado."
- **Selección por filtro**: se filtró por `status=submitted` (2 de los 3 registros), se activó "Seleccionar todos los que coinciden con el filtro (2)", se generó — segunda llamada real al mismo endpoint, 200 OK.
- **Falla parcial** (vía API directa, ya que la UI nunca mandaría un id inexistente): un lote con los 3 registros reales + un id inventado devolvió 200, ZIP con 3 PDF + `manifest.csv` con 3 filas `success` y 1 `failed` ("Registro no encontrado").
- **Tope excedido** (vía API directa): un lote de 201 ids contra el tope por defecto de 200 devolvió 422 con "El lote excede el máximo permitido (200 registros)...".
- **Regresión**: se confirmó que `GenerateActaPanel` (generación de un solo registro, ya cerrado en docs/109) sigue funcionando igual tras los cambios en `acta_service.py`/`acta.py`.
- Se eliminó la plantilla de prueba directo en la base de datos demo (no existe endpoint DELETE, mismo precedente que docs/109); `backend/.env` y `frontend/.env.local` se revirtieron.
