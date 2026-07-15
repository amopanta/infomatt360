# 105. Arreglos de seguridad — Auditoría técnica de julio de 2026

## Qué cierra esto

El usuario compartió un documento externo, `AUDITORIA_TECNICA_INTEGRAL_INFOMATT360.md`, con un diagnóstico completo de arquitectura, seguridad, escalabilidad y cumplimiento de requisitos. Antes de actuar sobre cualquiera de sus hallazgos, se verificaron directamente contra el código 3 de los más concretos (no se aceptó el documento a ciegas): los 3 resultaron reales. El usuario pidió arrancar por esos 3 arreglos de seguridad (categoría "A" de la evaluación), dejando expresamente fuera de esta sesión las categorías de infraestructura real (multi-réplica, PgBouncer, pruebas de carga — requieren decisiones de hosting que no existen en el repositorio) y los refactors grandes y riesgosos (dividir `User` en 6 entidades, migrar todo a `AsyncSession`) por ir contra el patrón incremental de bajo riesgo de este proyecto y no tener todavía evidencia real de dolor (nunca se ha corrido una prueba de carga).

## S-001 — Guardado Runtime sin permiso explícito de escritura

**Antes:** `POST /runtime/save` (`backend/app/api/v1/runtime.py`) solo llamaba `require_template_access`, que internamente usa `assignment_service.user_has_project_access` — valida que el usuario tenga *alguna* asignación activa en el proyecto, sin importar qué permisos tenga esa asignación. Un usuario con un rol de solo lectura (`records.read` sin `records.write`) podía guardar registros.

**Ahora:** se agregó `require_project_permission(db, current_user.id, payload.project_id, RECORDS_WRITE)` explícito, mismo patrón ya usado en `correct_runtime_record_field` (el enlace mágico de corrección) en el mismo archivo.

**Efecto colateral honesto:** 4 archivos de prueba antiguos (`test_linked_subform_and_serial_number.py`, `test_mvp_builder_runtime_flow.py`, `test_participant_history.py`, `test_runtime_records.py`) creaban sus usuarios de prueba con una `UserProjectAssignment` **sin `role_id`** — funcionaba porque antes solo se validaba presencia de asignación, no permisos. Se les agregó un `Role` con `records.write` para que seguir representando correctamente a un usuario que captura datos.

## S-003 — Cada uso de API key escribía en base de datos

**Antes:** `api_key_service.authenticate()` (`backend/app/services/api_key_service.py`) hacía `row.last_used_at = utc_now(); db.add(row); db.commit()` en cada solicitud autenticada exitosamente, sin excepción — bajo alto volumen (integraciones bulk, dispositivos de campo) eso presiona I/O de la base de datos sin necesidad real.

**Ahora:** el commit solo ocurre si `last_used_at` es `None` o tiene más de `LAST_USED_AT_WRITE_INTERVAL_SECONDS` (60s) de antigüedad. `last_used_at` es puramente informativo (la revocación usa `status`/`revoked_at`, no depende de esto), así que una precisión de un minuto es más que suficiente. Solución más simple que la propuesta original del documento de auditoría (cola de escritura asíncrona) — se prefirió la opción mínima que resuelve el problema real sin agregar infraestructura nueva.

## S-004 — API keys sin expiración

**Antes:** las claves solo se podían revocar manualmente; no existía una fecha de vencimiento.

**Ahora:** `ProjectApiKey.expires_at` (nullable — una clave sin expiración se comporta exactamente igual que antes, no rompe integraciones ya emitidas). `POST /api-keys/` acepta `expires_at` opcional (rechaza con 422 si no es una fecha futura). `authenticate()` rechaza una clave vencida igual que una revocada. El estado `"expired"` se calcula al leer (`_effective_status`), nunca se escribe en la base — evita gastar una escritura extra solo por el paso del tiempo, coherente con el espíritu de S-003.

**Bug real encontrado solo probando en el navegador, no por las pruebas automatizadas:** la primera versión de `create_key` comparaba `payload.expires_at <= utc_now()` directo. El frontend envía la fecha con `Date.toISOString()`, que **siempre** incluye el sufijo `Z` (datetime consciente de zona horaria); `utc_now()` en este proyecto devuelve deliberadamente un datetime *sin* zona (`datetime.now(timezone.utc).replace(tzinfo=None)`, documentado así en `app/core/time.py` por compatibilidad con las columnas `DateTime` existentes). Comparar un datetime consciente de zona contra uno sin zona lanza `TypeError` en Python — eso producía un `500` que el navegador reportaba como `Failed to fetch` / `net::ERR_FAILED`, sin cuerpo de error legible. La prueba automatizada original no lo detectó porque construía la fecha con `utc_now().isoformat()` (sin zona, por venir de la misma función), así que nunca ejercitó la combinación real de tipos que sí produce el frontend. Se corrigió normalizando cualquier fecha entrante a UTC sin zona (`_to_naive_utc`) antes de comparar o guardar, y se corrigió también la prueba para que envíe una fecha consciente de zona (igual que el frontend real) — ver la nota en el propio test.

## Frontend

`ApiKeysApp.tsx` (`/admin/api-keys`, pantalla que ya existía) agregó el campo opcional "Expira en (días)" al formulario de creación, y la tarjeta de cada clave ahora muestra su fecha de expiración y usa el `status` efectivo devuelto por el backend (`"expired"` se ve y se comporta como inactiva — el botón "Revocar" desaparece igual que para una clave ya revocada).

## Pruebas

- `backend/tests/test_runtime_save_requires_records_write.py` (nuevo): un usuario de solo lectura recibe `403` al intentar `POST /runtime/save`; un usuario con `records.write` puede guardar normalmente.
- `backend/tests/test_api_keys.py::test_api_key_expiration` (nuevo): rechaza `expires_at` en el pasado (422); crea una clave con expiración futura; confirma que sigue siendo válida antes de vencer; simula el vencimiento y confirma `401` en `/api-keys/auth/check` y `status: "expired"` en el listado, sin que `status` en la base de datos se haya reescrito.
- Los 4 archivos de prueba afectados por el endurecimiento de S-001 se actualizaron para asignar un rol real con `records.write` a sus usuarios de prueba.
- Suite completa: 353 pruebas en verde (2 nuevas), mismos 5 errores preexistentes no relacionados (caché de pytest bloqueado en Windows).

## Verificación en vivo

Contra el backend y frontend reales de la demo:

- **S-001:** se creó un usuario y un rol de solo lectura (`records.read`) por API, se le asignó al proyecto demo, y se confirmó `403 Permiso insuficiente` al intentar `POST /runtime/save`; el usuario administrador demo (con `records.write`) sí pudo guardar normalmente.
- **S-003:** se creó una API key real, se hicieron dos llamadas a `/api-keys/auth/check` separadas por 1 segundo y se confirmó en la base de datos que `last_used_at` **no cambió** entre ambas; luego se retrasó artificialmente ese valor a más de 60 segundos y se confirmó que la siguiente llamada **sí** lo actualizó.
- **S-004:** se creó una API key real desde la UI real con expiración a 30 días — la tarjeta mostró la fecha correcta ("Expira: 14/8/2026"). Al probar por primera vez se encontró el bug de `TypeError` naive/aware descrito arriba (`Failed to fetch` real en el navegador); se corrigió, se confirmó el recargue automático del backend (`WatchFiles detected changes... Reloading`), y se repitió la creación con éxito. Se retrasó artificialmente `expires_at` a un minuto en el pasado directamente en la base de datos, se recargó la pantalla, y la tarjeta mostró `expired` (sin botón "Revocar"), confirmando que el estado se calcula en vivo sin necesitar una escritura de vencimiento.

Todos los datos de prueba (usuario, rol, asignación y registro del caso S-001; las dos API keys de prueba de S-003/S-004) se eliminaron de la base de datos de la demo al finalizar.

## Qué queda pendiente (categorías fuera de esta sesión, ver evaluación del documento de auditoría)

- Sincronización por lotes desde sesión de usuario (no API key) para el cliente offline — hallazgos SYNC-001 a SYNC-005.
- Infraestructura real de escalado (réplicas, PgBouncer, Redis obligatorio, observabilidad Prometheus/Grafana) — requiere que exista un entorno de hosting real, que hoy no está definido en el repositorio.
- Pruebas de carga formales (3.000 usuarios concurrentes / 300.000 solicitudes) — no ejecutables sin un entorno de staging equivalente a producción.
- Refactors grandes de arquitectura (descomponer `User`, migrar a `AsyncSession`) — deliberadamente pospuestos hasta tener evidencia real de que son el cuello de botella, no antes.
