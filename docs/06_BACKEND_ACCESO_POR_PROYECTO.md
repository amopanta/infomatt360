# Backend - Acceso por Proyecto

## Objetivo
Garantizar que los modulos de InfoMatt360 respeten el aislamiento por proyecto.

## Archivos agregados

```text
backend/app/api/project_access.py
backend/app/api/v1/project_context.py
backend/app/schemas/project_context.py
```

## Dependencia principal

```python
require_project_access(project_id)
```

Valida:

- token JWT valido;
- usuario activo;
- asignacion activa del usuario al proyecto.

## Endpoint de validacion

```text
GET /api/v1/projects/{project_id}/access
```

## Uso futuro

Esta dependencia debe usarse en modulos como:

- formularios;
- participantes;
- registros;
- evidencias;
- reportes;
- integraciones;
- escritorio;
- sincronizacion Android.

## Pendientes

- validar accion especifica dentro del proyecto;
- validar permisos por formulario;
- validar permisos por registro;
- validar permisos por territorio;
- agregar roles jerarquicos;
- agregar auditoria de accesos denegados.
