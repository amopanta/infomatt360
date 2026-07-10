# Backend - Acceso por Proyecto

## Objetivo
Garantizar que los modulos de InfoMatt360 respeten el aislamiento por proyecto.

## Estado actual

La sesion autenticada devuelve los proyectos activos asignados al usuario:

```text
GET /api/v1/auth/session
```

Cada proyecto incluye:

- `id`;
- `name`;
- `role_id`;
- `permissions`.

El frontend guarda el proyecto activo, los permisos del proyecto y la lista de
proyectos de la sesion. Con eso:

- filtra el menu administrativo;
- bloquea rutas administrativas directas sin permiso;
- muestra selector de proyecto en el encabezado cuando hay mas de un proyecto;
- recalcula permisos al cambiar de proyecto.
- limpia proyecto, permisos y lista de proyectos al cerrar sesion.

El backend sigue validando permisos y alcance en cada endpoint. La validacion
del frontend solo mejora experiencia de usuario.

## Dependencias de permisos

```python
require_project_permission(db, user_id, project_id, permission)
require_any_project_permission(db, user_id, project_id, permissions)
require_any_permission(db, user_id, permissions)
```

Validan:

- token JWT valido;
- usuario activo;
- asignacion activa del usuario al proyecto;
- permisos del rol activo.

## Uso recomendado

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

- normalizar catalogo de permisos en un documento unico;
- validar permisos por formulario;
- validar permisos por registro;
- validar permisos por territorio;
- agregar roles jerarquicos;
- agregar auditoria de accesos denegados.
