# Dashboard operativo

## Objetivo

Convertir la ruta inicial de InfoMatt360 en un resumen util del proyecto activo.

## Endpoint

```text
GET /api/v1/dashboard/projects/{project_id}/summary
```

La consulta exige autenticacion y asignacion activa al proyecto. Devuelve:

- formularios totales y publicados;
- registros totales y distribucion por estado;
- usuarios activos asignados;
- evidencias y almacenamiento consumido;
- los ocho registros mas recientes.

## Interfaz

La ruta `/` muestra tarjetas de metricas, actividad reciente y accesos directos
a formularios, registros, usuarios y evidencias. La ruta `/records` permite
seleccionar un formulario, buscar capturas y expandir todos sus valores.

La vista de registros permite descargar un CSV UTF-8 compatible con Excel. La
exportacion incluye todos los campos dinamicos y neutraliza celdas que comienzan
con caracteres de formula (`=`, `+`, `-`, `@`) para evitar CSV injection.

## Validacion

La prueba automatizada comprueba los conteos, la actividad reciente y el
aislamiento entre proyectos.
