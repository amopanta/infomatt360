# Backend - Flujos de Revision

## Objetivo
Crear la base para cambiar estados de registros y dejar historial de revision.

## Archivos agregados

```text
backend/app/models/review.py
backend/app/schemas/review.py
backend/app/services/review_service.py
backend/app/api/v1/review.py
backend/alembic/versions/0010_review.py
```

## Capacidades iniciales

- aplicar accion de revision sobre un registro;
- cambiar estado del registro;
- guardar estado anterior y nuevo;
- guardar observacion;
- guardar usuario que realizo la accion;
- consultar historial de acciones.

## Endpoints

```text
POST /api/v1/review/actions
GET /api/v1/review/records/{record_id}/actions
```

## Estados previstos

- draft;
- submitted;
- under_review;
- returned;
- corrected;
- approved;
- rejected;
- cancelled.

## Pendientes

- reglas de transicion;
- permisos por accion;
- aprobacion por niveles;
- notificaciones automaticas;
- validacion IA antes de aprobar;
- bloqueo de edicion despues de aprobado.
