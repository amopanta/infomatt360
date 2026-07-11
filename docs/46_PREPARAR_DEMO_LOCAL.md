# Preparar demo local

## Objetivo

Crear una base SQLite demo limpia, aplicar todas las migraciones y cargar datos
demo sin borrar bases locales antiguas.

## Comando

Desde la raiz del proyecto:

```powershell
.\scripts\prepare-demo.cmd
```

## Que hace

- Usa `backend\.venv`.
- Aplica `alembic upgrade head` sobre `sqlite:///./infomatt360_demo.db`.
- Ejecuta la semilla demo idempotente.
- Actualiza `backend\.env` para que `DATABASE_URL` apunte a la base demo.

## Credenciales

- Usuario: `admin@infomatt360.demo`
- Clave: `Demo12345!`
- Proyecto: `demo-project-infomatt360`

El rol demo incluye permisos administrativos amplios para validar el MVP:
usuarios, constructor, registros, flujos de aprobacion, API keys,
sincronizacion bulk, metricas operativas, reportes, mapas y mensajes.

## Nota

Si existe una base antigua `infomatt360_dev.db`, este script no la elimina. La
base demo queda separada para evitar choques con esquemas previos.
