# Captura híbrida: devoluciones, reasignación, observaciones y exportación limpia

Estado: especificación aprobada para implementación; NO certificada ni desplegada.
Rama de trabajo: feature/hybrid-offline-capture-20261017.

## Reglas innegociables

1. Borrador: editable por el recolector autorizado. Enviado o en revisión: bloqueado para recolectores. Devuelto: editable exclusivamente por el recolector destinatario de la devolución. Reenviado: bloqueado. Aprobado: bloqueado, salvo flujo administrativo excepcional separado y auditado.
2. Conservar siempre `runtime_records.id`, `submitted_by` (autor original), historial de versiones y evidencias; reasignar una corrección NO debe alterar el autor original ni crear otra aplicación.
3. Coordinador puede devolver/reasignar dentro de su ámbito territorial/equipo; administrador según permisos. Un gestor distinto solo accede al registro devuelto expresamente a su usuario.
4. Las observaciones son datos de calidad independientes de las respuestas `runtime_record_values`. No se inyectan como preguntas ni campos de la plantilla.
5. La exportación ordinaria de respuestas es **limpia**: respuestas y claves técnicas, sin comentarios, motivos, devoluciones ni auditoría. Filtro de estado, con opción predeterminada aprobados para reportes oficiales. Exportación separada de observaciones; exportación de auditoría solo explícita.
6. Una observación puede apuntar a un campo, a un ítem concreto de REPEAT (ruta e identificador estable), a una evidencia o al registro general. Debe registrar motivo, acción solicitada, revisor, fechas, estado y revisión asociada.
7. La importación Excel permite una fila por observación, múltiples observaciones por registro, `record_id` obligatorio, `action=RETURN_ORIGINAL|REASSIGN`, `target_user_id` cuando corresponda. Vista previa, validación por fila, idempotencia, reporte de rechazos, lotes y permisos; no aplicar cambios parciales silenciosamente.
8. Sincronización incremental por dispositivo: comparar versión de registro, versión de plantilla, estado, permisos, manifest de archivos y checksum. Si el destinatario ya tiene la versión completa, enviar solo estado/observaciones; si no, descargar respuestas y adjuntos faltantes. La existencia del participante NO prueba que exista el registro completo.
9. Una reasignación revoca la autorización anterior para correcciones posteriores, pero no borra copias locales. La escritura offline se revalida en servidor con versionado optimista; conflictos quedan en cuarentena sin sobrescritura.
10. La descarga de información y adjuntos debe restringirse a participantes, formularios y registros autorizados; cifrado local, caducidad/revocación de acceso y registro de descargas.

## Diseño de persistencia propuesto (nuevas entidades; NO creadas aún)

- `record_review_observations`: id, record_id, review_cycle_id, field_name nullable, repeat_item_key nullable, attachment_id nullable, note, requested_action, status, created_by, created_at, resolved_at, verified_by.
- `record_correction_assignments`: id, record_id, original_submitter_id, assigned_to_id, assigned_by_id, reason, status, grant_version, created_at, revoked_at.
- `record_sync_manifests`: record_id, content_version, template_version, attachment_manifest_hash; el estado del dispositivo se almacena localmente y se intercambia mediante cursor incremental.
- `review_bulk_jobs` y `review_bulk_job_items`: importación idempotente, previsualización, errores por fila y trazabilidad.

No agregar columnas de observaciones a `runtime_record_values`.

## Contratos API propuestos (NO implementados)

- `POST /api/v1/review/records/{id}/observations`
- `GET /api/v1/review/records/{id}/observations`
- `POST /api/v1/review/records/{id}/return` con `target_user_id` opcional (por defecto autor original).
- `POST /api/v1/review/returns/import/preview` y `POST /api/v1/review/returns/import/commit`
- `GET /api/v1/review/returns/mine`
- `GET /api/v1/runtime/sync/pull?cursor=...` y manifest por registro
- `GET /api/v1/exports/runtime/answers.csv` (limpia)
- `GET /api/v1/exports/runtime/observations.csv` (observaciones independientes)

## Aceptación mínima antes de producción

- Exportación de respuestas no contiene ninguna columna de observación, aunque haya 5 observaciones por registro; una fila de registro no se multiplica por la unión con observaciones.
- Exportación de observaciones incluye 5 filas para ese registro, con IDs estables y nombre de pregunta.
- Gestor original puede editar borrador, no enviado; solo devuelto si es destinatario; aprobado bloqueado.
- Coordinador devuelve a gestor original: dispositivo con datos completos recibe solo diferencias.
- Coordinador reasigna a otro gestor sin datos: recibe registro, REPEAT, matriz y adjuntos íntegros.
- Reasignación no modifica `submitted_by`; permisos por territorio, proyecto y rol comprobados.
- Dos tablets offline no pueden sobrescribir silenciosamente versiones distintas.
- Excel de 1.000 filas con errores devuelve reporte detallado y no genera duplicados al reintentar.
- El gestor ve las observaciones y navega a la página, pregunta e ítem REPEAT exactos.
- Probar APIs, frontend, móvil, escritorio, PWA y sincronización con pérdida de red.

## Dependencias existentes a reutilizar

- `backend/app/api/v1/review.py`, `backend/app/services/review_service.py`
- `backend/app/api/v1/runtime.py`, `backend/app/services/runtime_record_service.py`
- `backend/app/api/v1/form_assignments.py`
- `backend/app/models/runtime_record.py`
- `frontend/src/modules/records/RecordsApp.tsx`
- `frontend/src/modules/offline/indexedDbQueue.ts`, `offlineSync.ts`
- `desktop/src/offlineQueue.js`

**Brecha existente:** `PATCH /runtime/record/{id}/correction` hoy comprueba `records.write` y el estado; antes de habilitar devoluciones a terceros debe comprobar el destinatario de la devolución y la versión de autorización, no solo el permiso general.
