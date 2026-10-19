# Integración incremental de capacidades comparadas con CommCare

Este trabajo amplía los módulos existentes de InfoMatt360. No crea un segundo servicio de casos, participantes, mensajería ni exportaciones, y no retira rutas actuales.

## Contratos actuales y destino

| Capacidad | Módulo existente que se extiende | Estado |
| --- | --- | --- |
| Casos tipados y relación padre/hijo | `ParticipantCase`, `/cases` | Primer incremento implementado; falta editor visual de vínculos entre participantes. |
| Exportación consolidada de casos | `SavedExport`, `run_saved_export`, `worker-scheduler` | Primer incremento implementado en CSV, con filtro territorial y frecuencia existente. |
| Actualización de casos desde formularios | `runtime_record_service.save_record` + `BuilderTemplate` | Pendiente: contrato de mapeo explícito por plantilla, idempotencia y auditoría antes de activar. |
| Casos sin conexión | Cola local y sincronización por lotes de Runtime | Pendiente: snapshot de propiedades, versión por caso, resolución de conflictos y pruebas en dos dispositivos. |
| Compartir casos entre equipos | `GestorTeam`, asignaciones de participantes y permisos | Pendiente: reglas de visibilidad y transferencia que no amplíen el acceso territorial. |
| SMS, IVR y encuestas bidireccionales | `message_service`, conectores y scheduler | Pendiente: proveedor, consentimiento, costos y recepción verificable; no se simula con WhatsApp. |
| Detección configurable de casos duplicados | Detección de participante/documento y `duplicate_flag` | Pendiente: reglas por tipo/propiedades, revisión humana y prohibición de fusionar automáticamente. |
| Jerarquía territorial configurable | `UserTerritory` y filtros de permisos | Pendiente: árbol por proyecto y auditoría de todas las rutas de lectura/exportación. |
| Edición/importación masiva de casos | Carga Excel y motor de casos | Pendiente: vista previa, versión esperada, validación por fila y registro de cambios. |
| Alertas condicionales por propiedades | `ScheduledTask` y canales existentes | Pendiente: predicados configurables, control de repeticiones y destinatarios. |

## Compatibilidad del primer incremento

- Los casos existentes reciben `case_type=general` y `parent_case_id=NULL`.
- Las exportaciones existentes conservan su significado: `summary` sin formulario y `form` con formulario.
- `export_kind=cases` usa el programador y los archivos guardados actuales; el CSV contiene el estado vigente de cada caso y sus propiedades JSON.
- Un hijo solo puede vincularse a un padre del mismo proyecto, visible para el usuario. La lectura de hijos vuelve a filtrar cada participante por territorio.
- La exportación de casos se filtra por los participantes autorizados al destinatario, también cuando se ejecuta automáticamente.

## Validación

Las pruebas de `test_case_management.py` cubren la creación y lectura de casos hijos, el filtro territorial y la exportación de casos con el programador existente. La migración `0080_case_relations_and_exports` debe aplicarse antes de arrancar una imagen que use las nuevas columnas.

El primer incremento no constituye equivalencia con CommCare. En particular, la cola sin conexión actual guarda formularios, no cambios de casos. No debe anunciarse sincronización longitudinal de casos hasta disponer de pruebas reales de desconexión y conflictos.
