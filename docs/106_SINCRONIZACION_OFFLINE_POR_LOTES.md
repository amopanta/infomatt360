# 106. Sincronización offline por lotes

## Qué cierra esto

Categoría B del documento de auditoría técnica externa de julio 2026 (ver docs/105 para la categoría A ya cerrada). Dos hallazgos, acotados por decisión explícita del usuario:

- **SYNC-001 (severidad Crítica):** tanto el escritorio (`desktop/src/offlineQueue.js::syncPending`) como el navegador/PWA (`frontend/src/modules/offline/offlineSync.ts::syncNow`) sincronizaban registro por registro con un `for...await` secuencial contra `POST /runtime/save`. Con 1.000 registros pendientes a ~700ms de latencia media, eso son ~12 minutos. El propio código ya documentaba esto como "riesgo aceptado" en un comentario.
- **SYNC-004:** ninguna de las dos colas locales tenía índices reales. `indexedDbQueue.ts::listPending()` hacía `store.getAll()` y filtraba en JS (full scan). La cola de escritorio (SQLite vía sql.js) sí filtraba con `WHERE status = 'pending'` en SQL, pero sin índice era un recorrido completo de la tabla a partir de cierto volumen.

**SYNC-002 ya estaba resuelto**, confirmado leyendo el código (sin cambios de código en esta sesión): el cliente offline ya usaba `/runtime/save` con sesión de usuario normal, nunca la API key del endpoint bulk existente — `offlineQueue.js` ya tenía un comentario documentando que intentar `/runtime/bulk/save` con sesión de usuario devolvía `401 "API key requerida"` en una prueba real anterior.

**SYNC-003** (reintento automático en segundo plano) y **SYNC-005** (limpieza automática de registros sincronizados) quedan fuera de esta sesión por decisión explícita del usuario — son cambios de *comportamiento* (actividad de red automática / borrado automático de datos locales), no solo optimizaciones, y merecen su propia decisión de UX.

## Diseño

### Backend: `POST /runtime/session/bulk-save`

No se reimplementó el motor de carga masiva — ya existía completo para integraciones con API key: `runtime_record_service.save_records_bulk()`, que acepta hasta 10.000 registros por lote, `idempotency_key` opcional, y procesa cada item con el mismo `save_record()` que usa la captura individual (mismo peaje de validación: duplicados, participante, flujo de aprobación). El único endpoint que lo exponía (`POST /runtime/bulk/save`) exige API key — pensado para integraciones externas, no para la sesión de un usuario normal.

Nuevo endpoint, mismo archivo (`backend/app/api/v1/runtime.py`), junto a `save_runtime_record`:
- Auth: sesión normal (`get_current_user`), no API key.
- Exige `records.write` explícito (`require_project_permission`), mismo permiso que ya exige el guardado individual (S-001, docs/105).
- Valida que la plantilla exista y pertenezca al proyecto.
- Llama `save_records_bulk(db, payload, current_user.id)` — a diferencia del endpoint de API key (que pasa `user_id=None`), aquí se pasa el usuario real para que `submitted_by` quede correctamente atribuido.

### Cliente: agrupar por (proyecto, plantilla) + idempotencia de lote

Los registros pendientes locales pueden pertenecer a distintas plantillas (un usuario puede capturar varios formularios sin conexión). Antes de sincronizar, `offlineSync.ts::syncNow` (rama navegador/PWA) y `offlineQueue.js::syncPending` (escritorio) agrupan los pendientes por `(projectId, templateId)` y mandan **un** `POST /runtime/session/bulk-save` por grupo, no uno por registro. Los resultados por item (`results[].index` correlaciona con el orden enviado) determinan qué registro local queda `synced` y cuál queda `pending` con su error — mismo resultado observable (`{attempted, synced, failed}`) que antes, con 1 request por grupo en vez de 1 por registro.

**Idempotencia del lote:** cada grupo calcula un `idempotency_key` = SHA-256 de sus ids locales ordenados (mismo algoritmo en ambos clientes — `crypto.subtle.digest` en el navegador, `node:crypto` en escritorio). Si la respuesta se pierde en la red después de que el servidor ya creó los registros, un reintento con el mismo conjunto de ids reutiliza la respuesta cacheada (`BulkImportJob`, mecanismo ya existente en `save_records_bulk`) en vez de duplicar — cierra el "riesgo aceptado" que el propio código de `offlineQueue.js` ya documentaba desde antes.

### Índices en las colas locales (SYNC-004)

- **IndexedDB** (`indexedDbQueue.ts`): `DB_VERSION` subió a 2; `onupgradeneeded` crea índices `status` y `createdAt` sobre el object store existente (maneja tanto una base nueva como una ya existente en v1, sin perder datos). `listPending()` pasa de `getAll()` + `filter` a `store.index('status').getAll('pending')`.
- **SQLite de escritorio** (`offlineQueue.js`): `CREATE INDEX IF NOT EXISTS` sobre `status` y `created_at`, junto al `CREATE TABLE IF NOT EXISTS` existente. La consulta SQL de `listPending` no cambió (ya filtraba bien con `WHERE`), el índice solo la hace barata a escala.

De paso se corrigió un comentario desactualizado al inicio de `offlineQueue.js` que decía "reutiliza `POST /runtime/bulk/save`" cuando el código real usaba `/runtime/save` — quedaba desactualizado otra vez si no se actualizaba al endpoint nuevo real.

## Pruebas

- `backend/tests/test_runtime_session_bulk_save.py` (nuevo, 5 pruebas): exige `records.write`; crea registros atribuidos al usuario real (`submitted_by`); la `idempotency_key` evita duplicar en un reintento (`replayed: true`, mismo conteo de registros); rechaza una plantilla de otro proyecto (422) y una plantilla inexistente (404).
- `frontend/src/modules/offline/offlineSync.test.ts` (reescrito, 6 pruebas): un solo request a `/runtime/session/bulk-save` para varios registros pendientes de la misma plantilla (antes probaba explícitamente que era `/runtime/save`, un request por registro); dos plantillas distintas generan dos lotes separados; un registro reportado como fallido dentro del lote queda pendiente sin afectar a los demás; error HTTP o de red deja todo el lote pendiente.
- `desktop/src/offlineQueue.test.js` (reescrito, 8 pruebas): mismas aserciones que el lado navegador, adaptadas a Node/sql.js.

## Verificación en vivo

Contra el backend y frontend reales de la demo, con navegador real: se escribieron 3 registros de prueba directo en la IndexedDB real del navegador (mismo esquema exacto que produce `enqueueRecord`, incluyendo los índices nuevos), se recargó la aplicación con sesión real (`admin@infomatt360.demo`), se confirmó que el botón "Sincronizar pendientes (3)" ya reflejaba el conteo correcto vía el índice `status`, y se hizo clic. La pantalla mostró "Sincronizados 3 de 3". Se confirmó en `read_network_requests` que se hizo **una sola llamada** a `POST /runtime/session/bulk-save` (más el preflight `OPTIONS`) — cero llamadas a `/runtime/save` — con una `idempotency_key` real de 64 caracteres hexadecimales y los 3 resultados (`created`) correlacionados por índice. Se confirmó en la base de datos real que los 3 `RuntimeRecord` quedaron creados con `submitted_by = 'demo-admin-user'` (el usuario real de la sesión, no `NULL` como en el endpoint de API key). Todos los datos de prueba (los 3 registros, sus valores, el `BulkImportJob` de idempotencia, y la base IndexedDB local de prueba) se eliminaron al finalizar.
