# 103. Carga masiva de asignaciones (usuario-proyecto-rol) por Excel

## Qué cierra esto

El hallazgo #2 de la auditoría de trazabilidad ([docs/96](96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md)): el Documento Maestro de Requerimientos (§10) pide carga masiva por Excel de asignaciones usuarios↔proyectos↔formularios↔territorios↔dispositivos↔permisos. Antes de este cambio, `excel_import_service.py` solo soportaba `participants` y `users`; `assignment_service.py` solo tenía alta individual, sin importador.

## Alcance de esta versión (acordado con el usuario)

El requisito original describe una matriz de asignación mucho más amplia de lo que el código soporta hoy — **no existen** modelos de "formulario asignado", "territorio" ni "dispositivo" como entidades propias (`Territory`, `Device` no existen en `app/models/`). Construirlos habría sido un feature aparte, mucho más grande. Se acotó a lo que sí existe y era el hueco explícito señalado en la auditoría: **carga masiva de asignaciones usuario+proyecto+rol** (`UserProjectAssignment`), reutilizando el motor de importación Excel genérico que ya existía para participantes/usuarios.

## Cómo funciona

Se agregó un tercer `entity_type`, `"assignments"`, al mismo pipeline subir→previsualizar→mapear→aprobar de `excel_import_service.py` (`ENTITY_ALIASES`, `REQUIRED_FIELDS`, `ASSIGNMENT_TARGET_FIELDS`) — mismo flujo, mismos permisos (`identity.users.manage`, ya protegía todo el router de `excel-import`), sin endpoints nuevos.

Columnas esperadas: `correo`/`email` (obligatorio) y `rol`/`nombre del rol` (obligatorio), con `estado`/`status` opcional (por defecto `"active"`). El proyecto destino es el mismo parámetro `project_id` que ya recibe el resto del importador (un archivo = un proyecto, igual que participantes/usuarios) — no hay columna de proyecto por fila.

A diferencia de `entity_type="users"` (que crea usuarios nuevos), la carga de asignaciones **asume que el usuario y el rol ya existen**: busca el usuario por correo (`identity_service.get_user_by_email`, insensible a mayúsculas) y el rol por nombre (insensible a mayúsculas), y crea la fila `UserProjectAssignment` correspondiente. Si el usuario no existe, la fila falla con `"No existe un usuario con el correo '...'"`; si el rol no existe, falla con `"No existe un rol llamado '...'"` — ambos casos quedan en el reporte de errores del lote sin detener las demás filas, igual que el resto del importador.

**Honestidad:** no hay deduplicación. Si la misma fila se importa dos veces, o el usuario ya tenía una asignación activa en el proyecto, queda una fila `UserProjectAssignment` más — mismo comportamiento que crear una asignación individual hoy (`POST /assignments/` tampoco deduplica). No se resolvió aquí porque es un comportamiento preexistente, no algo que este cambio introduce.

## Frontend

`ExcelImportApp.tsx` (`/admin/excel-import`) ya era una pantalla real con UI (a diferencia de las dos features anteriores de esta sesión, que eran 100% API) — se agregó la opción "Asignaciones (usuario-proyecto-rol)" al selector de tipo de entidad y sus campos destino (`email`, `role_name`, `status`) al paso de mapeo de columnas.

## Pruebas

`backend/tests/test_excel_import.py`: nueva prueba que sube un Excel con 3 filas (una asignación válida, un correo inexistente, un rol inexistente), confirma el mapeo automático de columnas (`Correo`→`email`, `Rol`→`role_name`), aprueba el lote, y verifica `imported_rows == 1`, `failed_rows == 2` con los dos mensajes de error esperados, más la fila `UserProjectAssignment` real creada en la base de datos con el rol correcto.

## Verificación en vivo

Contra el backend y frontend reales de la demo, **usando la UI real** (a diferencia de las dos features anteriores, que no tenían pantalla): se creó un usuario de prueba nuevo por API (sin ninguna asignación previa), se generó un Excel real con `openpyxl` con una fila válida para ese usuario (rol "Administrador demo") y una fila con un correo inexistente, se inyectó el archivo en el `<input type="file">` de la pantalla `/admin/excel-import` (los inputs de archivo no aceptan valores programáticos por seguridad del navegador, así que se sirvió el archivo real desde un servidor HTTP local temporal y se inyectó vía `fetch` + `DataTransfer`, evitando cualquier alteración de bytes), se seleccionó "Asignaciones (usuario-proyecto-rol)" en el selector, se subió, se confirmó que el mapeo automático detectó las columnas correctamente y que el paso de mapeo mostraba las tres opciones nuevas (`email`, `role_name`, `status`), se confirmó el mapeo y se aprobó — la UI mostró "Importacion completada: 1 importada(s), 1 fallida(s)" con el mensaje de error exacto esperado, y se confirmó en la base de datos que la fila `UserProjectAssignment` real quedó creada con el rol correcto. De paso, durante esta verificación se encontraron y limpiaron un rol, un usuario y una asignación huérfanos de una sesión de verificación anterior (nombrados "... (verificacion temporal)", del 2026-07-14) que nunca se habían limpiado — no relacionados con este cambio. Todos los datos de prueba de esta sesión y los huérfanos previos se eliminaron de la base de datos de la demo al finalizar.
