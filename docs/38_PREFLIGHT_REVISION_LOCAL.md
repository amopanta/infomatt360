# Preflight de revision local

## Objetivo

Validar rapidamente que la rama local de InfoMatt360 esta lista para una demo
o revision tecnica.

## Comando

```powershell
.\scripts\preflight.cmd
```

## Que valida

- existencia de archivos criticos;
- sintaxis de scripts PowerShell;
- suite backend completa con `pytest`;
- sintaxis TypeScript offline;
- estado de dependencias frontend;
- `git diff --check`.

## Resultado esperado

El comando termina con:

```text
Preflight OK para revision local.
```

Si `frontend\node_modules` no existe, lo reporta como advertencia porque la
instalacion npm depende de acceso al registro externo. El chequeo de sintaxis
TypeScript offline sigue ejecutandose con la cache local disponible.
