# 101. Jerarquía de roles: Administrador nacional / Auditor de solo lectura

## Qué cierra esto

El hallazgo #12 de la auditoría de trazabilidad ([docs/96](96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md)): el Documento Maestro de Requerimientos (§21) pide una jerarquía de roles con **Administrador nacional** (sobre todas las organizaciones), **Administrador de proyecto** y **Auditor/Consulta** de solo lectura. Antes de este cambio, `Role` era un catálogo plano de permisos y `UserProjectAssignment` ataba un rol a un único proyecto — no existía forma de dar acceso a *todos* los proyectos de una organización sin asignar el rol proyecto por proyecto, ni un rol de solo-lectura predefinido.

**Alcance decidido con el usuario:** "Administrador nacional" = una Organización, todos sus Proyectos (no cruza a otras organizaciones — respeta el tenant lógico `Organization` ya decidido, no un superadmin global). "Administrador de proyecto" ya existía (cualquier rol asignado vía `UserProjectAssignment`); no requirió cambios.

## Diseño

En vez de inventar un tipo de rol especial, **"Administrador nacional" es cualquier rol asignado a nivel de Organización en vez de a nivel de Proyecto** — la nacionalidad viene de *cómo* se asigna, no de un flag nuevo en `Role`. Se agregó un modelo hermano de `UserProjectAssignment`:

```python
class UserOrganizationAssignment(Base):
    __tablename__ = "user_organization_assignments"
    id, user_id, organization_id, role_id, status, created_at
```

La resolución de permisos por proyecto (`app/api/permissions.py::get_project_permissions`) ahora **une** los permisos del rol asignado directamente al proyecto con los del rol asignado a nivel de la organización dueña de ese proyecto. Esto da acceso automático a todo proyecto existente y futuro de la organización, sin asignaciones individuales — se verificó explícitamente que un proyecto creado *después* de la asignación de organización queda cubierto igual, porque la consulta se resuelve en cada request, no se cachea.

`assignment_service.user_has_project_access` (usada por ~25 endpoints vía `require_template_access` y equivalentes) recibió el mismo fallback: si no hay una fila directa de `UserProjectAssignment`, revisa si existe una `UserOrganizationAssignment` activa para la organización dueña del proyecto. Al corregirse en este único punto central, todos los endpoints que dependen de ella heredan el soporte sin tocarlos uno por uno.

`require_permission_in_organization` y `get_user_organization_ids` (usadas por las pantallas ya existentes de branding/backups/storage/tenant-clean a nivel organización) también se extendieron para reconocer una asignación de organización directa, no solo la derivada de asignaciones de proyecto.

## Rol predefinido "Auditor/Consulta"

`backend/app/services/installation_service.py` ahora siembra un segundo rol junto al "Administrador" de siempre, en toda organización nueva creada por el instalador: **Auditor/Consulta**, con permisos `projects.read, records.read, gis.read, messages.read, reports.export` — solo lectura y exportación de reportes, sin escritura, aprobación, anulación ni gestión de nada. Queda disponible desde el arranque sin que un admin tenga que ensamblar la lista de permisos a mano. (La base de datos demo de este proyecto se sembró con `seed_demo.py`, no con el instalador real, así que no lo tiene automáticamente — se creó uno equivalente ad hoc solo para la verificación en vivo, ver abajo.)

## Fix de seguridad encontrado de paso

Explorando `app/api/v1/assignments.py` para este cambio se encontró que `POST/GET /assignments/` (crear/listar asignaciones proyecto↔usuario↔rol) **no tenía ningún chequeo de permiso** — cualquier usuario autenticado podía asignarse a sí mismo cualquier rol en cualquier proyecto. No lo introdujo esta feature, pero es directamente adyacente (mismo archivo, misma capa de autorización) y de una sola línea por endpoint, así que se corrigió aquí: ambos endpoints ahora exigen `identity.users.manage`, igual que el resto de la gestión de identidad. El nuevo `POST/GET /organization-assignments/` se protegió desde el inicio con `organizations.manage` (el mismo permiso que ya protege `POST /identity/roles`).

## Fuera de alcance (deliberado)

No existe ninguna UI de frontend para crear roles o asignaciones, ni antes ni después de este cambio — `POST /identity/roles` y `POST /assignments/` no tienen ningún caller en `frontend/src`, es territorio 100% API gestionado por quien tenga el permiso correspondiente. Esta feature sigue ese mismo patrón. Si más adelante se quiere una pantalla de gestión de usuarios/roles, sería un trabajo aparte.

## Pruebas

`backend/tests/test_organization_assignments.py` (7 pruebas): una asignación de organización da acceso a todos sus proyectos sin asignación individual; cubre un proyecto creado *después* de la asignación; el rol Auditor/Consulta puede leer pero un intento de revisar/aprobar un registro da 403; una asignación de organización en la Organización A **no** da acceso a un proyecto de la Organización B (aislamiento cruzado); una asignación de proyecto normal sigue funcionando sin ninguna asignación de organización (no regresión); crear una asignación de organización exige `organizations.manage`; y `POST /assignments/` ahora exige `identity.users.manage` (regresión del hueco de seguridad encontrado). `backend/tests/test_installation.py` se extendió para confirmar que el instalador siembra el rol "Auditor/Consulta" con el set de permisos exacto.

## Verificación en vivo

Contra el backend real de la demo (sin UI de frontend involucrada, ver "Fuera de alcance"): se creó una organización de prueba con dos proyectos nuevos, un usuario asignado *solo* a nivel de organización con un rol amplio, y se confirmó por API que accedía a ambos proyectos (`200`) sin ninguna asignación individual. Se creó un segundo usuario con un rol equivalente a "Auditor/Consulta" asignado a nivel de organización: pudo leer el resumen de un proyecto (`200`) pero un intento de crear un rol (acción de gestión) dio `403` por faltarle `organizations.manage`. Se confirmó que el primer usuario (nacional de la organización de prueba) **no** tenía acceso al proyecto demo de una organización distinta (`403`, aislamiento cruzado). Se confirmó que `POST /assignments/` sin `identity.users.manage` ahora da `403` (el fix de seguridad). Todos los datos de prueba (organización, proyectos, roles, usuarios, asignaciones) se eliminaron de la base de datos de la demo al finalizar.
