# Instalacion y build frontend

Este paso descarga las dependencias de Vite, React, TypeScript y Vitest. Requiere acceso al registro npm.

## Comando recomendado

Desde la raiz del proyecto:

```powershell
.\scripts\install-frontend.cmd
```

El script ejecuta:

1. `npm install --no-audit --no-fund --progress=false`
2. `npm run build`

En Windows, el script fuerza `NODE_OPTIONS=--use-system-ca` para que npm use
los certificados raiz del sistema. Esto evita el error
`UNABLE_TO_VERIFY_LEAF_SIGNATURE` sin desactivar la validacion SSL.

## Si la instalacion se queda esperando

En esta estacion ya se valido que el codigo frontend no tiene errores de sintaxis TypeScript con el chequeo offline del preflight. Si `npm install` se agota por tiempo, el bloqueo probable es conectividad con el registro npm, no un error del proyecto.

Reintentar cuando haya mejor conexion o un proxy corporativo configurado:

```powershell
cd frontend
npm.cmd install --no-audit --no-fund --progress=false
npm.cmd run build
```

Si aparece `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, probar:

```powershell
$env:NODE_OPTIONS="--use-system-ca"
npm.cmd install --no-audit --no-fund --progress=false
npm.cmd run build
```

## Validacion actual sin internet

El preflight ejecuta una validacion TypeScript offline usando la cache local disponible en `..\work\tscheck`.

```powershell
.\scripts\preflight.cmd
```
