# Backups programables desde la web

## Objetivo

Disparar y consultar respaldos de la base de datos desde el navegador
(ademas de los scripts de linea de comandos existentes en
[63_BACKUP_RESTORE_POSTGRES.md](63_BACKUP_RESTORE_POSTGRES.md)), dejando un
historial consultable de cada ejecucion.

## Modelo

`BackupJob` (`backend/app/models/backup.py`): `project_id`,
`storage_profile_id` (opcional), `status` (`running`/`completed`/`failed`),
`file_path`, `size_bytes`, `triggered_by`, `error`, `started_at`,
`finished_at`. Es un registro de resultado, no un programador: la
recurrencia (si se necesita) se resuelve reutilizando `ScheduledTask` con
`task_type="backup"` cuando exista un worker que lo dispare.

## Como corre el respaldo

`backup_service.run_backup()` detecta el motor por `settings.database_url`:

- **SQLite** (desarrollo/demo): copia directa del archivo con
  `shutil.copyfile`.
- **PostgreSQL** (produccion): invoca `pg_dump --format=custom` via
  `subprocess.run` con la lista de argumentos explicita (nunca
  `shell=True`, para evitar inyeccion de comandos). La contrasena se pasa
  por la variable de entorno `PGPASSWORD`, nunca como argumento de linea de
  comandos (evita que quede visible en `ps`/logs de proceso).

El archivo se guarda en `settings.backup_directory` (la misma carpeta
`backups/` ignorada por Git que usan los scripts de `pg_dump`/`pg_restore`).

## Endpoints

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/api/v1/backups/run?project_id=...` | `backups.manage` |
| `GET` | `/api/v1/backups/project/{project_id}` | `backups.manage` |

## Pantalla en el frontend

`frontend/src/modules/admin/BackupsApp.tsx` (ruta `/admin/backups`,
permiso `backups.manage`): boton "Ejecutar respaldo ahora" que dispara
`POST /backups/run` para el proyecto activo, y una tabla con el historial
(inicio, estado, tamaño, ruta del archivo, error si aplica). Cliente API
en `frontend/src/modules/admin/backupsApi.ts`.

Verificado contra backend real (demo sobre SQLite): el boton ejecuto la
copia del archivo, el resultado aparecio de inmediato en la tabla con
estado "Exitoso" y el tamaño real del archivo generado.

## Limites conocidos

- Un backup fallido (ej. `pg_dump` no esta en el `PATH` del servidor) queda
  registrado con `status="failed"` y el error truncado a 4000 caracteres en
  `BackupJob.error`, pero no reintenta automaticamente.
- No hay restauracion desde la web todavia: para restaurar, usar
  `scripts/restore-postgres.cmd` (ver doc 63) con el archivo generado aqui.
