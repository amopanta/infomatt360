# Eliminar un formulario desde administración

Ruta: **Formularios → abrir formulario → Configuración → Eliminar formulario**. Solo se muestra a usuarios con `identity.users.manage` en el proyecto. Para confirmar hay que escribir el nombre exacto del formulario.

La eliminación retira el formulario de los listados, impide nuevas capturas y bloquea edición, duplicación y acceso a su vista de captura. No borra respuestas históricas ni auditoría: esos datos permanecen para trazabilidad. A diferencia de **Archivar**, no existe un botón para restaurarlo desde la interfaz.

API: `POST /api/v1/builder/templates/detail/{template_id}/delete` con `{"name":"Nombre exacto"}`. El servidor valida proyecto, permiso y confirmación, registra `delete_template` en auditoría y cambia el estado a `deleted`. Los listados del constructor y el conteo de formularios omiten ese estado. Los endpoints de captura y administración de plantilla devuelven 404; la consulta de respuestas ya existentes sigue disponible según sus permisos.
