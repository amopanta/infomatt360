# 102. Base Espejo real (replicación a base de datos externa)

## Qué cierra esto

El hallazgo #1 de la auditoría de trazabilidad ([docs/96](96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md)) — el más grande y más caro de los pendientes. El Documento Maestro de Requerimientos (§17) pide replicación hacia una base de datos externa (Postgres/MySQL/SQL Server/SQLite/ODBC), con prueba de conexión, creación de estructura equivalente y sincronización programada/por eventos en modos insert-only/incremental/espejo completo/respaldo analítico.

Antes de este cambio, `app/models/mirror.py` (`MirrorTarget`, `MirrorPlan`) y `app/services/mirror_service.py` eran solo CRUD — sin motor real, sin conexión a nada, y `conn_json` se guardaba **en texto plano**. Nadie lo usaba desde el frontend (cero llamadas en `frontend/src`, igual que roles/asignaciones — ver [docs/101](101_JERARQUIA_DE_ROLES_ORGANIZACION.md)).

## Alcance de esta versión (acordado con el usuario)

- **Motores:** Postgres y SQLite. Postgres porque `psycopg2-binary` ya estaba instalado (cero dependencias nuevas) y es el destino típico para BI/analítica (Power BI/Metabase/Superset, hallazgo #9). SQLite porque no requiere driver adicional y sirve de espejo local/de pruebas.
- **Estructura del espejo:** misma estructura EAV que el motor interno — replica `runtime_records`/`runtime_record_values` (el motor de captura real, no el modelo `Record` legado) tal cual, con prefijo `im360_` en las tablas destino (`im360_runtime_records`, `im360_runtime_record_values`) para no chocar con datos propios del cliente en esa base.
- **Modos de sincronización:** `full_mirror` (espejo completo: borra y reinserta todas las filas del proyecto en cada corrida) e `insert_only` (agrega solo lo nuevo por id, nunca toca ni borra lo existente — bueno para logs inmutables).
- **Disparo:** manual, vía `POST /mirror/plans/{id}/run`.

**Pendiente, documentado honestamente (no resuelto aquí):** MySQL y SQL Server (requieren instalar `pymysql`/`pyodbc`, no es solo código), modo incremental (por marca de tiempo), "respaldo analítico" como modo distinto, una tabla ancha pivotada por plantilla (más cómoda para BI directo, pero exige DDL dinámico por formulario), integración con `ScheduledTask` para sincronización programada/recurrente (hoy solo manual), y — igual que roles/asignaciones — no hay UI de frontend.

## Fixes de seguridad encontrados de paso

Reconstruyendo esta área se encontraron y corrigieron dos problemas del código existente:

1. **Credenciales en texto plano.** `MirrorTargetRead` heredaba el campo `conn_json` directo de `MirrorTargetCreate`, así que cualquiera con acceso de lectura al proyecto vería usuario/contraseña de la base externa tal cual se guardó. Ahora `MirrorTargetConnect` recibe credenciales estructuradas por motor, el servicio las cifra con `encrypt_text` (`app/core/security.py`, el mismo mecanismo ya usado para credenciales S3 en `s3_storage_service.py` y tokens OAuth de Google Drive) antes de guardarlas, y `MirrorTargetRead` solo expone `id, project_id, name, engine, status` — nunca el secreto.
2. **Permiso faltante.** `POST /mirror/plans` y `GET /mirror/plans/{target_id}` no tenían ningún chequeo de acceso a proyecto (a diferencia de `POST/GET /mirror/targets`, que sí lo tenían). Se agregó un permiso nuevo, `mirror.manage`, que ahora protege los 7 endpoints del módulo.

## Cómo funciona

`POST /mirror/targets` valida los datos de conexión según el motor (`host`/`database`/`username` para Postgres, `file_path` para SQLite), cifra las credenciales y crea el destino con `status="pending"`. `POST /mirror/targets/{id}/test-connection` abre una conexión real (`SELECT 1`) y actualiza `status` a `"active"` o `"connection_error"` según el resultado — nunca persiste nada más. `POST /mirror/plans` crea un plan de sincronización sobre un destino ya conectado, en modo `full_mirror` o `insert_only`. `POST /mirror/plans/{id}/run` ejecuta la sincronización ahora mismo: crea la estructura equivalente en el destino si no existe (`metadata.create_all(engine, checkfirst=True)`, agnóstico de motor vía SQLAlchemy Core), lee los `RuntimeRecord`/`RuntimeRecordValue` del proyecto, y aplica el modo correspondiente. Cada corrida queda registrada en `MirrorRun` (mismo patrón que `BackupJob` en `app/models/backup.py`: `status="running"` al crear, se cierra a `"completed"`/`"failed"` con contadores y error) — `GET /mirror/plans/{id}/runs` da el historial completo, y `MirrorPlan.last_result` da un resumen rápido de la última corrida sin abrir el historial.

## Pruebas

`backend/tests/test_mirror.py` (7 pruebas, todas contra SQLite real — sin necesitar Postgres disponible en el entorno de pruebas): conectar un destino exige `mirror.manage` y `MirrorTargetRead` nunca incluye credenciales; probar conexión contra un archivo SQLite real tiene éxito y dispara `status="active"`; probar conexión contra un host Postgres inalcanzable falla con `502` y deja `status="connection_error"` (sin necesitar un servidor Postgres real — solo un host que no responde); una corrida en modo `full_mirror` replica registros y valores reales verificados leyendo el archivo SQLite espejo directamente con `sqlite3`; correr dos veces en `full_mirror` no duplica filas; en modo `insert_only`, modificar un valor en el origen y correr de nuevo **no** toca la fila ya espejada pero sí agrega un registro nuevo; el historial de corridas se lista correctamente.

## Verificación en vivo

Contra el backend real de la demo (sin UI de frontend, mismo patrón que roles/asignaciones): se creó un registro de prueba real en `demo-project-infomatt360`, se conectó un destino SQLite apuntando a un archivo temporal, se probó la conexión (`200`, `success: true`, `status` pasó a `active`), se creó un plan en modo `full_mirror` y se ejecutó — la corrida devolvió `status: completed` con 7 registros y 24 valores sincronizados (todo el dataset real del proyecto demo, no solo el registro nuevo). Se abrió el archivo SQLite resultante directamente (fuera de la app, con `sqlite3` puro) y se confirmó que `im360_runtime_records`/`im360_runtime_record_values` contenían el registro de prueba con sus valores reales (`nombre: "Hogar Prueba Espejo"`, `integrantes: 6`). Se confirmó el historial de corridas. No se pudo verificar contra un Postgres real porque no hay un servidor Postgres accesible en este entorno — la conexión fallida contra Postgres sí se verificó (ver pruebas), y la construcción de la URL de conexión (`postgresql+psycopg2://...`) es la misma sintaxis estándar de SQLAlchemy, pero un ciclo completo de sincronización contra un Postgres real queda sin probar en vivo. Todos los datos de prueba (registro, destino, plan, corrida, archivo SQLite temporal) se eliminaron al finalizar.
