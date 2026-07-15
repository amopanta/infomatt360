# 104. Carga masiva de registros históricos por Excel

## Qué cierra esto

El hallazgo #3 de la auditoría de trazabilidad ([docs/96](96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md)): el Documento Maestro de Requerimientos (§10) pide carga masiva de registros/respuestas históricas o externas por Excel, "pasando por el mismo peaje de validación" que una captura normal. Antes de este cambio existía `save_records_bulk` (sincronización JSON vía API-key, para dispositivos/lotes ya estructurados), pero no un importador desde un archivo `.xlsx` crudo.

## Diferencia con las cargas masivas anteriores (participantes/usuarios/asignaciones)

Aquellas mapean a un conjunto **fijo** de campos destino (`document_id`, `full_name`, etc.). Aquí el conjunto de campos destino es **dinámico**: depende de qué plantilla (`BuilderTemplate`) se esté important — cada formulario tiene sus propios campos (`BuilderComponent.name`). Por eso `entity_type="records"` exige indicar `template_id` al subir el archivo, y el mapeo de columnas se construye contra los campos *de esa plantilla*, no contra una lista fija.

## "Mismo peaje de validación"

Se logra reutilizando directamente `runtime_record_service.save_record()` — el mismo método que usa la captura real desde Runtime — para cada fila del Excel, en vez de insertar `RuntimeRecord`/`RuntimeRecordValue` a mano. Esto da gratis, sin reimplementar nada:

- enlace automático de participante por `DOCUMENT_ID` (docs/98);
- detección de posible duplicado por `content_hash` (docs/77) — nunca bloquea, solo marca `duplicate_flag`;
- snapshot del flujo de aprobación activo del proyecto;
- asignación de consecutivos (`SERIAL_NUMBER`) si el formulario los usa.

## Alcance de esta versión (acordado con el usuario)

- **Tipos de campo soportados — solo escalares simples** (una celda de Excel = un valor): `TEXT, TEXTAREA, DOCUMENT_ID, EMAIL, PHONE, URL, SELECT, DROPDOWN, DATE, TIME, DATETIME, YEAR, MONTH, WEEK, NUMBER, INTEGER, DECIMAL, PERCENTAGE, CURRENCY, RATING, NPS, RANGE, BOOLEAN`. Estos ni siquiera aparecen en el selector de mapeo de columnas: `FILE, IMAGE, PDF, MULTIFILE, AUDIO, VIDEO, SIGNATURE, GPS, GEOTRACE, GEOSHAPE, REPEAT, LINKED_SUBFORM, MATRIX, LIKERT_5, LIKERT_7, CALCULATE, REFERENCE, PARENT_CHILD, LOOKUP, HIDDEN, UUID, RESPONSE_ID, INTERVIEW_DURATION, CAPTURED_BY, CHANGE_HISTORY, BARCODE, QR, OCR, RANKING, MULTISELECT, SERIAL_NUMBER` — documentados como pendientes.
- **Fecha histórica — columna opcional.** Si el Excel trae una columna de fecha (alias `fecha`/`fecha historica`), el `RuntimeRecord` importado conserva esa fecha real como `created_at` en vez de la fecha de la carga — es la diferencia central entre "carga de históricos" y "captura nueva". El `RuntimeRecordCreate`/`save_record` compartidos (usados también por la captura pública en vivo desde Runtime) **no se modificaron** para esto — la fecha histórica se aplica con un `UPDATE` directo y acotado sobre el registro recién creado, solo dentro de esta ruta de importación, para no abrir la puerta a fechar registros retroactivamente desde la captura normal.

## Cómo funciona

Se agregó un cuarto `entity_type`, `"records"`, al mismo pipeline subir→previsualizar→mapear→aprobar de `excel_import_service.py`. `POST /excel-import/upload` ahora acepta `template_id` (obligatorio solo para `entity_type="records"`, valida que la plantilla pertenezca al proyecto). El mapeo dinámico se construye consultando `BuilderComponent` de esa plantilla, filtrado a los tipos escalares simples, con auto-detección de columnas por coincidencia del `label` del campo — igual que el resto del importador. Se agregan dos campos destino reservados: `_meta_status` ("Estado (opcional)", por defecto `submitted`) y `_meta_created_at` ("Fecha histórica (opcional)"). Cada valor de campo mapeado se coacciona al tipo JSON correcto según el tipo de campo (texto → string, numérico → número, `BOOLEAN` → booleano reconociendo si/no/true/false/1/0). Una fila sin ningún valor de campo mapeado no crea un registro — se reporta como error de fila.

`ExcelImportJobRead` ahora incluye `target_fields` (poblado solo para `entity_type="records"`) — el frontend lo usa para pintar el selector de mapeo dinámico en vez de una lista fija de campos, con las etiquetas reales de la plantilla.

## Frontend

`ExcelImportApp.tsx` (`/admin/excel-import`) agregó la opción "Registros históricos de un formulario", que muestra un selector de plantilla (reutiliza `fetchProjectTemplates`, ya usado igual por `PublicLinksApp.tsx` y `XlsformApp.tsx`) antes de habilitar la subida.

## Pruebas

`backend/tests/test_excel_import.py` (4 pruebas nuevas): `template_id` es obligatorio para `entity_type="records"`; los campos destino excluyen un componente `GPS` de la plantilla de prueba (tipo no soportado); un lote válido crea `RuntimeRecord`/`RuntimeRecordValue` reales, con un campo numérico guardado como JSON número (no string), una fila con columna de fecha histórica deja `created_at` igual a esa fecha real, una fila sin esa columna queda con la fecha de la carga, y una fila cuyo `DOCUMENT_ID` coincide con un `Participant` ya existente del proyecto queda enlazada (prueba directa de que se reutiliza `save_record`, no una reimplementación paralela); una fila sin ningún valor mapeado se reporta como error sin crear registro.

## Verificación en vivo

Contra el backend y frontend reales de la demo, usando la UI real: se generó un Excel con `openpyxl` con las columnas reales de la plantilla `Caracterizacion demo` (`Nombre del hogar`, `Numero de integrantes`, `Observaciones`) más una columna `Fecha` para el historial, con 2 filas (una con fecha histórica `2019-08-20`, otra sin fecha). Se inyectó el archivo en el `<input type="file">` de la pantalla (mismo método de servidor HTTP local temporal + `fetch`/`DataTransfer` usado en la verificación de docs/103, para evitar corrupción de bytes por transcripción manual), se seleccionó "Registros históricos de un formulario" y la plantilla real, se subió, y se confirmó que el paso de mapeo mostraba las etiquetas reales de los campos (`Nombre del hogar`, `Numero de integrantes`, `Observaciones`, `Estado (opcional)`, `Fecha histórica (opcional)`) y que el campo `GPS` ("Ubicacion") de la plantilla real no aparecía como opción. El mapeo automático detectó correctamente las 4 columnas, incluida `Fecha`→`_meta_created_at`. Se aprobó el lote: "Importacion completada: 2 importada(s), 0 fallida(s)". Se confirmó en la base de datos real que el registro con fecha histórica quedó con `created_at = 2019-08-20 00:00:00` exacto, el registro sin fecha quedó con la fecha real de la carga, y el valor de `integrantes` quedó guardado como JSON número (`5`, sin comillas) y no como string. Todos los datos de prueba (los 2 registros, sus valores, y el lote de importación) se eliminaron de la base de datos de la demo al finalizar.
