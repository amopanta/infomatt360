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
recurrencia se resuelve reutilizando `ScheduledTask` con
`task_type="backup"` -- ver "Respaldo automatico" abajo para el worker que
ahora sí lo dispara.

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
| `POST` | `/api/v1/scheduler/tasks` (`task_type="backup"`) | `backups.manage` |
| `GET` | `/api/v1/scheduler/tasks/{project_id}` | acceso al proyecto |

## Respaldo automatico: el worker que faltaba

**Correccion**: la version inicial de este modulo dejaba `ScheduledTask`
como una tabla de configuracion sin ningun proceso que la leyera --
programar una frecuencia no disparaba nada; el unico respaldo real seguia
siendo el boton manual. `scheduler_service.run_due_tasks()`
(`backend/app/services/scheduler_service.py`) cierra ese hueco:

- Frecuencias recurrentes soportadas: `hourly`, `daily`, `weekly`
  (`RECURRING_INTERVALS`). `manual` (el default del modelo) nunca se
  recoge automaticamente -- sigue siendo solo el boton de la web.
- Al crear una tarea recurrente sin `next_run_at` explicito, se programa
  para el proximo ciclo del worker (no para dentro de un intervalo
  completo), de modo que el primer respaldo real llega pronto y no un dia
  despues de configurarlo.
- Por cada tarea vencida (`next_run_at <= ahora`): ejecuta
  `backup_service.run_backup()` (usando `target_id` como
  `storage_profile_id` si se configuro uno), registra un `TaskRun` con el
  resultado, y recalcula `next_run_at = ahora + intervalo`.
- Un `task_type` sin dispatcher soportado (hoy solo existe `backup`) se
  registra como `TaskRun` fallido con un mensaje explicito, en vez de
  fallar silenciosamente o lanzar una excepcion.

### Worker CLI

```
python -m app.cli.run_scheduled_tasks              # un solo ciclo
python -m app.cli.run_scheduled_tasks --loop --sleep-seconds 60
```

Mismo patron que `app/cli/process_bulk_jobs.py`: un proceso separado del
servidor web, para que un `pg_dump` de varios minutos nunca bloquee una
peticion HTTP. En produccion se deja corriendo con `--loop` (via
supervisor/systemd/cron), sondeando cada minuto por defecto.

`POST /scheduler/tasks` con `task_type="backup"` ahora exige el permiso
`backups.manage` (antes solo pedia pertenencia al proyecto, inconsistente
con el boton manual que sí lo exige desde el principio).

## Pantalla en el frontend

`frontend/src/modules/admin/BackupsApp.tsx` (ruta `/admin/backups`,
permiso `backups.manage`): seccion "Respaldo automático" con un selector
de frecuencia (cada hora/diario/semanal) y boton "Programar respaldo
automático" (`POST /scheduler/tasks`); si el proyecto ya tiene un respaldo
programado, muestra su frecuencia, proxima ejecucion y ultimo resultado en
vez del formulario. Debajo, el boton "Ejecutar respaldo ahora" (manual) y
la tabla de historial de siempre. Cliente API en
`frontend/src/modules/admin/schedulerApi.ts` y
`frontend/src/modules/admin/backupsApi.ts`.

Verificado contra backend real: se programo un respaldo diario desde la
UI, se corrio `python -m app.cli.run_scheduled_tasks` una vez, y el
respaldo se ejecuto de verdad (copia de 1.1MB del archivo SQLite de
demo) -- la pantalla, al recargar, mostro el resultado en "Último
resultado" y en la tabla de historial, con `next_run_at` recalculado para
24 horas despues.

## Limites conocidos

- Un backup fallido (ej. `pg_dump` no esta en el `PATH` del servidor) queda
  registrado con `status="failed"` y el error truncado a 4000 caracteres en
  `BackupJob.error`, pero no reintenta automaticamente antes de la
  siguiente ejecucion programada.
- No hay endpoint para editar o pausar una tarea programada ya creada
  (solo `POST` para crear y `GET` para listar); para cambiar la
  frecuencia hoy hay que hacerlo directamente en la base de datos.
- No hay restauracion desde la web todavia: para restaurar, usar
  `scripts/restore-postgres.cmd` (ver doc 63) con el archivo generado aqui.
- El worker no es un demonio del sistema operativo: alguien debe dejarlo
  corriendo con `--loop` (supervisor/systemd/cron) en el servidor de
  produccion; el codigo por si solo no se autoinicia.
