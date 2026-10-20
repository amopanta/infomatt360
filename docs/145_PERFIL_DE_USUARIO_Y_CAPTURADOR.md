# 145. Perfil de usuario y datos de quien captura

Fecha: 2026-10-19. Rama: `feature/hybrid-offline-capture-20261017`.

## Qué se pidió

1. Al crear un usuario deben ir, como mínimo:
   - número de documento;
   - nombre completo;
   - cargo;
   - municipio.

   Así los informes por usuario (como el avance de metas) salen completos.
2. Que los formularios guarden esos datos de quien captura sin configurar nada.

## Integración del PR #46

La pantalla de creación de cuentas venía en el PR #46 («Administración de
usuarios por proyecto»), que no estaba unido. Se integró en esta rama y se
resolvieron 9 archivos en conflicto:

- **Asignaciones:**
  - se conserva la vía del administrador de plataforma (H11);
  - se adopta la regla del #46, más estricta: nadie entrega un rol con permisos que no tenga en ese proyecto;
  - si la persona ya tiene asignación, se responde 409.
- **Pantallas de registros, ERP y usuarios:** se conservan las traducciones y se usan las etiquetas de estado, fechas y nombres de gestor del #46.

El PR #46 queda incluido aquí y puede cerrarse sin unir.

## Perfil del usuario

| Dato | Obligatorio al crear | Dónde |
|---|---|---|
| Número de documento | Sí (ya lo era; único) | `users.document_id` |
| Nombre completo | Sí (ya lo era) | `users.full_name` |
| Cargo | **Sí (nuevo)** | `users.position` |
| Departamento y municipio | **Sí (nuevo)** | `users.department`, `users.municipality` |
| Correo (con él se inicia sesión) | Sí | `users.email` |
| Teléfono | No | `users.phone` |

- **Usuarios → Crear usuario** pide todos los obligatorios. La casilla
  «Limitar su acceso a este municipio» viene marcada y crea además el
  territorio de acceso (`user_territories`). Se desmarca para coordinadores
  o personal nacional.
- El municipio del perfil es un dato para informes y no restringe el
  acceso. El acceso lo da el territorio.
- **Datos de la persona** (en cada usuario) corrige nombre, cargo, municipio
  y teléfono. Pide la contraseña administrativa y queda auditado con el valor
  anterior (`PATCH /security/admin/projects/{p}/users/{u}/profile`).
- Los usuarios creados antes de este cambio muestran el aviso «Faltan datos
  obligatorios» hasta que se completen.
- La importación de usuarios por Excel exige también `cargo`, `departamento`
  y `municipio`.

## Datos de quien captura en cada registro

Todo registro guarda automáticamente, sin agregar campos al formulario:
- nombre, documento, cargo, departamento y municipio de quien lo envió;
- tal como estaban al capturar (`runtime_records.captured_by_*`). Si después
  cambia el cargo o el municipio de la persona, sus registros anteriores no
  cambian.

Funciona igual en web, escritorio y app móvil, porque lo llena el servidor.

Dónde se ve:
- en el detalle del registro, «Capturado por»;
- en las exportaciones CSV (normal y limpia): columnas `capturado_por`,
  `capturador_documento`, `capturador_cargo` y `capturador_municipio`;
- en el Planeador (docs/144): el detalle por gestor y la hoja «Detalle por
  gestor» del Excel muestran documento y cargo. Si un gestor no tiene
  territorio asignado, se usa el municipio de su perfil.

El campo automático «Quién lo llenó» del constructor sigue disponible para
mostrar el nombre dentro del formulario.

## Migración

`0085_user_profile_capturer`, después de `0084_planner`:
- agrega 3 columnas a `users` y 5 a `runtime_records`;
- en los registros existentes llena nombre y documento con los datos
  actuales de quien los envió; el cargo y el municipio quedan vacíos porque
  no existían.

Se probó subir, bajar y volver a subir. En la base demo, 18 de 18
registros quedaron con capturador.

## Pruebas

- `tests/test_project_user_admin.py`:
  - cargo y municipio son obligatorios (422 sin ellos);
  - el perfil y el territorio se guardan;
  - se puede crear sin limitar el acceso;
  - la corrección del perfil pide la contraseña y queda auditada.
- `tests/test_capturer_snapshot.py`: el registro guarda el perfil de quien
  captura, no cambia si después cambia el perfil, y sale en el CSV.
- `tests/test_planner.py`: el Excel del planeador trae documento y cargo.
- Suite completa del backend: 549 pruebas. Web: 129 pruebas.
- Navegador, con la base demo: se creó «Laura Prueba Perfil», gestora social
  de Apartadó, y quedó con su territorio de acceso.
