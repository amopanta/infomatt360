# Equipos de gestores

Un **equipo de gestores** reúne usuarios responsables y participantes dentro de un proyecto. Es independiente del **grupo de participantes** (`group_name`) creado al importar o actualizar participantes. Una persona puede pertenecer a más de un equipo; la etiqueta de importación no cambia al agregarla o quitarla de un equipo.

## Uso

1. Abrir **Operación → Equipos de gestores** con permiso `identity.users.manage`.
2. Crear el equipo con un nombre único en el proyecto.
3. Marcar los gestores. Buscar participantes por nombre, documento, código o grupo de importación. Se pueden marcar individualmente o seleccionar todos los visibles.
4. Guardar integrantes. La pantalla permite cambiar el nombre o eliminar el equipo; las acciones quedan en auditoría.
5. Para asignar un formulario, abrir **Formularios → Configuración → Asignaciones por responsable → Asignar varios participantes**. Seleccionar un gestor miembro del equipo, elegir el método **Equipo de gestores**, validar la vista previa y confirmar.

La asignación masiva respeta la fuente del formulario, el territorio del gestor y los registros ya protegidos. Ser miembro de un equipo por sí solo no concede acceso a respuestas o formularios. La autorización sigue dependiendo de la asignación explícita `Formulario + Participante + Responsable` y de los permisos del usuario.

## API y datos

- `GET/POST /api/v1/gestor-teams/project/{project_id}`
- `PATCH/DELETE /api/v1/gestor-teams/{team_id}`
- `PUT /api/v1/gestor-teams/{team_id}/members` con `user_ids` y `participant_ids`.
- `POST /api/v1/form-assignments/templates/{template_id}/bulk-assign` con `mode=team`, `team_id` y `responsible_user_id`.

Tablas: `gestor_teams`, `gestor_team_users`, `gestor_team_participants`. Migración `0078_gestor_teams`. La actualización de integrantes reemplaza ambas listas de forma atómica después de validar que los usuarios tengan acceso al proyecto y que los participantes estén activos en él.
