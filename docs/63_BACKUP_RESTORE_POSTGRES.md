# Backup y restauracion PostgreSQL

## Objetivo

Definir un procedimiento minimo para respaldar y restaurar la base PostgreSQL
de InfoMatt360 antes de una salida a produccion, antes de migraciones y antes
de cambios de infraestructura.

## Scripts

```text
scripts/backup-postgres.cmd
scripts/restore-postgres.cmd
```

Ambos scripts requieren las herramientas cliente de PostgreSQL:

- `pg_dump`
- `pg_restore`

## Backup

Por defecto lee `DATABASE_URL` desde `.env.production` y genera un archivo
`.dump` en la carpeta `backups/`.

```powershell
.\scripts\backup-postgres.cmd -EnvFile .env.production
```

Tambien puede recibir la cadena directamente:

```powershell
.\scripts\backup-postgres.cmd -DatabaseUrl "postgresql+psycopg2://usuario:clave@host:5432/infomatt360"
```

El archivo generado usa formato custom de PostgreSQL (`pg_dump --format=custom`)
para permitir restauraciones mas controladas.

## Restauracion

La restauracion es una operacion destructiva si se apunta a una base con datos.
Por seguridad exige confirmacion explicita:

```powershell
.\scripts\restore-postgres.cmd `
  -BackupFile .\backups\infomatt360-infomatt360-20260703-120000.dump `
  -TargetDatabaseUrl "postgresql+psycopg2://usuario:clave@host:5432/infomatt360_restore" `
  -ConfirmRestore RESTORE
```

Recomendacion: probar primero en una base temporal/restaurada, nunca directo
sobre produccion sin ventana, backup vigente y aprobacion del responsable.

## Politica recomendada

- Backup antes de cada despliegue.
- Backup antes de cada migracion Alembic.
- Backup diario como minimo.
- Retencion segun criticidad del negocio.
- Restauracion probada periodicamente en ambiente no productivo.
- Registro del archivo, fecha, responsable y SHA256 si el backup se mueve entre
  servidores.

## Carpetas y seguridad

La carpeta `backups/` esta ignorada por Git. No subir dumps a repositorios ni
compartirlos por canales inseguros: pueden contener datos personales,
evidencias, tokens operativos o informacion sensible del proyecto.
