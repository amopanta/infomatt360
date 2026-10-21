# 146. Integración con bases de datos externas

Fecha: 2026-10-19. Rama: `feature/hybrid-offline-capture-20261017`.
Fuente: `Plan_Integracion_InfoMatt360_Sin_Perder_Avances.docx` (19-oct).
Decisión del plan: alternativa A, API REST y motor propio, sin reescribir el
núcleo.

## 1. Validación del plan contra el código

El plan partía de la bitácora del 17-oct, ya retirada. Esta es la situación
real antes de este cambio y lo que se hizo:

| Componente | Antes | Ahora |
|---|---|---|
| API Keys por proyecto (docs/53) | Existía | Sin cambios |
| API de lectura externa (docs/87) | Existía; participantes sin paginar | `limit`/`offset` opcionales en `/external-api/participants`; sin ellos responde igual que antes |
| API bulk de escritura (docs/54) | Existía | Sin cambios |
| Base espejo (docs/102) | Postgres, MySQL, SQL Server y SQLite en el código, pero **sin controladores de MySQL ni SQL Server instalados**. Solo copiaba registros en clave-valor | Se instalan `PyMySQL` y `pymssql`. Nuevo plan **«Proyecto completo»** (§2) con conciliación |
| Programador (scheduler) | Ya ejecutaba la base espejo (la bitácora lo daba como pendiente); corría cada 24 h desde que se creaba | Hora fija y zona horaria para tareas diarias o semanales (§4) |
| Importar desde una base externa | No existía | Participantes, respuestas de un formulario y asignaciones (§3) |
| Reglas y pipelines ETL (`/etl`) | Solo se guardaban; nada las ejecuta | Sin cambios. La importación nueva no los usa |

Lo que **no se modificó** (plan §5):
- autenticación, roles ni permisos;
- contratos existentes: un plan creado por API sin `scope` sigue siendo el
  espejo clave-valor;
- el modelo dinámico de formularios: las tablas por formulario se crean
  solo en la **base externa**, nunca en la principal;
- los módulos de participantes, ERP, BI, móvil ni reportes;
- el modo síncrono de SQLAlchemy.

## 2. Proyecto completo hacia otra base (una sola conexión)

**Avanzado → Base espejo:**
1. Crear el destino (PostgreSQL, MySQL/MariaDB, SQL Server o SQLite) y
   probar la conexión. Las claves se guardan cifradas.
2. **Nuevo plan → Qué copiar: «Proyecto completo»** y el modo:
   - **Espejo completo:** reemplaza lo del proyecto;
   - **Incremental:** solo registros nuevos o cambiados desde la corrida
     anterior;
   - **Solo inserción:** nunca reescribe.
3. **Ejecutar ahora** o **Programar**: diario o semanal a una hora y zona
   horaria, por ejemplo 02:00 America/Bogota.

No hay que configurar formulario por formulario. Cada corrida escribe en la
base externa:

| Tabla | Contenido |
|---|---|
| `im360_forms` | formularios del proyecto y el nombre de su tabla plana |
| `im360_form_fields` | diccionario de datos: pregunta, columna, etiqueta, tipo y orden |
| `im360_participants` | participantes con departamento, municipio y grupo |
| `im360_assignments` | asignaciones formulario ↔ participante ↔ responsable |
| `im360_records` | registros con estado, participante y quien capturó (docs/145) |
| `im360_record_values` | todas las respuestas en clave-valor, incluidos los grupos REPEAT |
| `im360_f_<formulario>_<id>` | **una tabla por formulario**, con una fila por registro y una columna por pregunta, más datos del participante y de quien capturó |

Comportamiento:
- Una pregunta nueva agrega su columna en la siguiente corrida; nunca se
  borran columnas.
- Las columnas van sin tildes y en minúsculas.
- Las respuestas complejas (archivos, GPS, grupos) quedan como JSON.
- Todas las tablas fijas llevan `project_id`, así varios proyectos pueden
  compartir la misma base externa.
- **Conciliación:** al terminar se cuentan las filas de origen y de destino
  de cada tabla. La pantalla muestra «Cuadra» o «Diferencia» por tabla, y la
  corrida queda como `completed` o `completed_with_differences`; una tarea
  programada con diferencias se registra como fallida.

## 3. Importar desde la base externa hacia InfoMatt360

En la misma pantalla, con un destino seleccionado: **Importar desde «…»**.

1. **Qué importar:**
   - Participantes;
   - Respuestas de un formulario;
   - Asignaciones de un formulario.
2. **Ver tablas de la base:** se listan las tablas y vistas reales (no se
   escribe SQL) y se elige una.
3. **Columnas:** se sugieren por nombre (por ejemplo, `cedula` →
   Documento). Se elige la **columna clave**, que identifica cada fila, y,
   si se quiere, una **columna de avance**: una fecha o un id creciente,
   para traer solo lo nuevo.
4. **Vista previa:** muestra qué pasaría con las primeras 20 filas (se crea,
   se actualiza, sin cambios, error) **sin escribir nada**.
5. **Ejecutar ahora** o **Programar diario** a una hora de Colombia.

Reglas:
- **Idempotencia:** cada fila importada se guarda con su clave y un hash
  (`db_import_keys`). Repetir la importación no duplica, y una fila sin
  cambios no se vuelve a escribir.
- **Participantes:** se crean o actualizan por documento o código dentro
  del proyecto.
- **Respuestas:**
  - se enlazan al participante por documento o código;
  - una fila que cambió actualiza su registro, con auditoría y versión;
  - **un registro aprobado no se modifica**;
  - el registro queda como capturado por quien creó la importación.
- **Asignaciones:** se busca el participante y al responsable por su correo.
  Se valida que el responsable pueda ver ese territorio.
- **Permisos:**
  - hace falta `mirror.manage` y el permiso de lo que se importa:
    `participants.create` o `identity.users.manage` para participantes,
    `records.write` para respuestas e `identity.users.manage` para
    asignaciones;
  - la importación corre en nombre de quien la creó, con su territorio;
  - si esa persona queda inactiva o pierde permisos, la importación deja de
    correr.
- **Historial:** cada corrida guarda filas leídas, creadas, actualizadas,
  sin cambios y con error, y el detalle de los errores (`db_import_runs`).
  También queda en la auditoría.

## 4. Programación a hora fija

Las tareas diarias y semanales aceptan en `config_json`
`{"run_time": "HH:MM", "timezone": "America/Bogota"}`. La próxima corrida es
la siguiente vez que sea esa hora en esa zona. Sin hora, corren cada 24 h,
como antes. Tipos nuevos de tarea: `db_import`.

## 5. Migración y dependencias

- `0086_db_sync`, después de `0085_user_profile_capturer`:
  - agrega `mirror_runs.summary_json`;
  - crea `db_imports`, `db_import_runs` y `db_import_keys`.

  Se probó subir, bajar y volver a subir.
- `requirements.txt`: `PyMySQL` y `pymssql`. Hay que reconstruir la imagen
  del backend para que los incluya.

## 6. Pruebas

`tests/test_db_sync.py`, 6 pruebas:
- proyecto completo hacia SQLite: tablas fijas, tabla por formulario con
  sus columnas, campos que solo están en respuestas, diccionario de datos,
  conciliación, columna nueva e incremental que escribe solo lo cambiado;
- el contrato anterior sin `scope` se conserva;
- las tablas compilan para PostgreSQL, MySQL (`LONGTEXT`) y SQL Server
  (`NVARCHAR(max)`);
- importación de participantes:
  - sugerencia de columnas;
  - vista previa sin escribir;
  - creación, actualización y fila con error;
  - repetición sin duplicar;
  - historial;
  - 403 sin `mirror.manage`;
- importación de respuestas y asignaciones:
  - participante inexistente;
  - repetición sin cambios;
  - aprobado no se modifica;
  - responsable inexistente;
- hora fija: 02:00 en Bogotá son 07:00 UTC;
- paginación de participantes en la API externa.

En total:
- suite completa del backend: 557 pruebas, incluidas las de `test_mirror.py`;
- web: 129 pruebas.

**Prueba real en el navegador** con la base demo y un SQLite externo:
- se exportó el proyecto completo en una corrida: 7 formularios y 7 tablas
  planas (la mayor con 57 preguntas), 18 registros, 95 respuestas,
  5 participantes y 5 asignaciones, todo cuadrado;
- se importó un padrón de 3 filas: 2 creados y 1 error por falta de nombre;
- al repetirlo quedaron 2 sin cambios, sin duplicar.

## 7. Límites y pendientes

- MySQL/MariaDB y SQL Server: los controladores quedan instalados y las
  tablas compilan para esos motores, pero la prueba real fue con SQLite.
  Falta una prueba contra un servidor de cada motor.
- Los participantes no tienen fecha de actualización: en cada corrida se
  copian completos. Lo mismo pasa con formularios, diccionario y
  asignaciones.
- Un registro borrado físicamente en InfoMatt360 no se borra en el destino
  incremental. Lo normal es anularlo, que sí viaja como cambio de estado.
- La importación lee hasta 50.000 filas por corrida. Para más, conviene una
  columna de avance.
- No hay sincronización bidireccional del mismo dato: exportar e importar
  son flujos separados (plan §8).
- Las reglas y pipelines ETL antiguos (`/etl`) siguen sin ejecutarse. Se
  pueden retirar más adelante.
