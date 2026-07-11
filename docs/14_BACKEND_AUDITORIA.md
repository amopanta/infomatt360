# Backend - Auditoria General

## Objetivo
Registrar acciones criticas del sistema para trazabilidad, soporte y control de calidad.

## Archivos agregados

```text
backend/app/models/audit.py
backend/app/schemas/audit.py
backend/app/services/audit_service.py
backend/app/api/v1/audit.py
backend/alembic/versions/0011_audit.py
```

## Capacidades iniciales

- registrar accion por usuario;
- asociar accion a proyecto;
- registrar modulo y accion;
- registrar entidad afectada;
- guardar antes y despues en JSON;
- guardar IP y dispositivo;
- listar auditoria por proyecto;
- filtrar por modulo.

## Endpoints

```text
POST /api/v1/audit/
GET /api/v1/audit/
```

## Vista operativa

La pantalla web `/audit` lista eventos recientes del proyecto seleccionado,
con filtro por modulo. La respuesta incluye `created_at` para ordenar y mostrar
fecha/hora del evento.

Cuando se consulta sin `project_id`, el backend limita la respuesta a eventos
globales/personales del usuario autenticado. Para auditoria operativa de
proyecto, la UI siempre envia `project_id` y el API valida asignacion activa.

## Pendientes

- integracion automatica en servicios;
- auditoria de accesos denegados;
- exportacion de logs;
- filtros avanzados;
- retencion por proyecto;
- alertas de actividad sospechosa.
