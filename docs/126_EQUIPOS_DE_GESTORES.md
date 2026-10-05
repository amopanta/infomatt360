# Equipos de gestores

Un **equipo de gestores** reúne usuarios responsables y participantes dentro de un proyecto. Es independiente del **grupo de participantes** (`group_name`) creado al importar o actualizar participantes. Una persona puede pertenecer a más de un equipo; la etiqueta de importación no cambia al agregarla o quitarla de un equipo.

## Uso

1. Abrir **Operación → Equipos de gestores** con permiso `identity.users.manage`.
2. Crear el equipo con un nombre único en el proyecto.
3. **Individual:** seleccionar un equipo, elegir `Gestor` o `Participante`, buscar por nombre, correo, documento o código y marcar o desmarcar la persona. La búsqueda devuelve hasta 50 coincidencias por vez para que la pantalla no cargue miles de filas.
4. **Masivo:** descargar la plantilla CSV en la misma pantalla. Tiene las columnas `equipo,tipo,identificador`. Cada fila asigna un gestor o participante a un equipo. `tipo` es `gestor` o `participante`. Para gestores, el identificador es correo o documento; para participantes, documento o código. El mismo archivo puede crear varios equipos. También se acepta `.xlsx` con esas tres columnas en la primera hoja. Máximo 50.000 filas y 10 MB por archivo.
5. Pulsar **Validar archivo** para ver equipos nuevos, integrantes nuevos, integrantes ya vinculados y errores por fila. **Confirmar carga masiva** solo queda disponible si no hay errores. La importación es atómica y repetir el mismo archivo no crea duplicados.
6. Para asignar un formulario, abrir **Formularios → Configuración → Asignaciones por responsable → Asignar varios participantes**. Seleccionar un gestor miembro del equipo, elegir el método **Equipo de gestores**, validar la vista previa y confirmar.

La asignación masiva respeta la fuente del formulario, el territorio del gestor y los registros ya protegidos. Ser miembro de un equipo por sí solo no concede acceso a respuestas o formularios. La autorización sigue dependiendo de la asignación explícita `Formulario + Participante + Responsable` y de los permisos del usuario.

## API y datos

- `GET/POST /api/v1/gestor-teams/project/{project_id}`
- `PATCH/DELETE /api/v1/gestor-teams/{team_id}`
- `PUT /api/v1/gestor-teams/{team_id}/members` con `user_ids` y `participant_ids`.
- `GET /api/v1/gestor-teams/project/{project_id}/summaries` y `GET /api/v1/gestor-teams/{team_id}/members/search` para listas ligeras y búsqueda individual.
- `POST/DELETE /api/v1/gestor-teams/{team_id}/members/{kind}` para asignación individual.
- `GET /api/v1/gestor-teams/project/{project_id}/bulk-template` y `POST /api/v1/gestor-teams/project/{project_id}/bulk-import` para plantilla, vista previa y carga masiva.
- `POST /api/v1/form-assignments/templates/{template_id}/bulk-assign` con `mode=team`, `team_id` y `responsible_user_id`.

Tablas: `gestor_teams`, `gestor_team_users`, `gestor_team_participants`. Migración `0078_gestor_teams`. La actualización de integrantes reemplaza ambas listas de forma atómica después de validar que los usuarios tengan acceso al proyecto y que los participantes estén activos en él.
