# Backend - Flujos de Revision

## Objetivo
Gestionar estados de registros, validar transiciones permitidas y dejar historial auditable de revision.

## Archivos agregados

```text
backend/app/models/review.py
backend/app/schemas/review.py
backend/app/services/review_service.py
backend/app/api/v1/review.py
backend/alembic/versions/0010_review.py
```

## Capacidades iniciales

- aplicar accion de revision sobre registros runtime y registros legados;
- validar que el registro exista antes de cambiar estado;
- validar que el registro pertenezca al proyecto informado;
- validar acceso del usuario al proyecto antes de aplicar o consultar acciones;
- validar permisos por accion sensible de revision;
- usar flujos configurables por proyecto/formulario cuando existan;
- limitar transiciones a un flujo seguro;
- guardar estado anterior y nuevo;
- guardar observacion;
- guardar usuario que realizo la accion;
- consultar historial de acciones desde API y desde la pantalla de Registros;
- registrar evento auditable asociado al cambio;
- notificar por mensaje interno al usuario que envio/creo el registro cuando otra persona cambia el estado.

## Endpoints

```text
POST /api/v1/review/actions
GET /api/v1/review/records/{record_id}/actions
GET /api/v1/review/records/{record_id}/next-actions
```

## Estados previstos

- draft;
- submitted;
- under_review;
- tech_approved;
- coordinator_approved;
- returned;
- corrected;
- approved;
- rejected;
- cancelled;
- archived.

## Transiciones permitidas

```text
draft -> submitted | cancelled
submitted -> under_review | approved | returned | rejected
under_review -> tech_approved | approved | returned | rejected
tech_approved -> coordinator_approved | approved | returned | rejected
coordinator_approved -> approved | returned | rejected
returned -> corrected
corrected -> under_review | submitted
approved -> archived
rejected -> archived
```

El flujo multinivel recomendado para procesos con control formal es:

```text
submitted -> under_review -> tech_approved -> coordinator_approved -> approved
```

## Permisos por accion

Ademas de pertenecer al proyecto, algunas transiciones requieren permisos del rol asignado al usuario:

```text
to_status=under_review          -> records.review o records.approve
to_status=tech_approved         -> records.review o records.approve
to_status=coordinator_approved  -> records.coordinate o records.approve
to_status=returned              -> records.review o records.approve
to_status=approved              -> records.approve
to_status=rejected              -> records.approve
to_status=archived              -> records.approve
```

Las acciones operativas de captura/correccion siguen disponibles para usuarios activos del proyecto:

```text
draft -> submitted
draft -> cancelled
returned -> corrected
corrected -> submitted
```

Esto evita que un usuario con acceso general al proyecto pueda aprobar, rechazar o archivar registros sin autoridad.

## Flujos configurables

Cuando existe un flujo configurable activo para el formulario o proyecto, el backend usa sus pasos para calcular la siguiente accion permitida. Si no hay flujo activo, usa el flujo predeterminado.

Ver documentacion extendida:

```text
docs/51_FLUJOS_APROBACION_CONFIGURABLES.md
```

## Interfaz

En la pantalla de Registros, al abrir el detalle de un registro se muestra:

- observacion de revision;
- acciones disponibles segun estado actual;
- historial de cambios de estado.

## Notificaciones internas

Cuando una accion de revision cambia el estado de un registro, el sistema crea un mensaje interno para el responsable del registro si:

- el registro tiene usuario propietario (`submitted_by` en runtime o `created_by` en registros legados);
- el propietario es diferente al usuario que aplico la accion;
- el propietario sigue activo en el proyecto.

El mensaje incluye:

- id del registro;
- estado anterior y nuevo;
- accion aplicada;
- observacion, si existe.

## Pendientes

- validacion IA antes de aprobar;
- bloqueo de edicion despues de aprobado.
