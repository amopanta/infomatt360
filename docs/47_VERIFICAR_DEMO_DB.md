# Verificar demo DB offline

## Objetivo

Confirmar que la base configurada en `backend\.env` esta migrada y contiene los
datos demo minimos sin levantar el backend HTTP.

## Comando

Desde la raiz del proyecto:

```powershell
.\scripts\check-demo-db.cmd
```

## Valida

- Version de Alembic esperada.
- Usuario, proyecto, rol y asignacion demo.
- Formulario demo y componentes.
- Registros y valores capturados.
- Capas y entidades GIS.
- Evidencia de archivo.
- Auditoria.

Si falla, ejecutar:

```powershell
.\scripts\prepare-demo.cmd
```
