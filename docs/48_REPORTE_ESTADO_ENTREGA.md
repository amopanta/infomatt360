# Reporte de estado de entrega

## Objetivo

Generar un archivo Markdown en `..\outputs` con una foto del estado actual:
doctor de entorno, demo DB, pruebas backend, frontend test/build, TypeScript
offline, whitespace y paquetes recientes. La validacion full stack se ejecuta
por separado con `.\scripts\check-full-stack.cmd` para evitar procesos anidados
en el reporte.

## Comando

Desde la raiz del proyecto:

```powershell
.\scripts\make-status-report.cmd
```

## Salida

Archivo similar a:

```text
..\outputs\infomatt360-status-YYYYMMDD-HHMMSS.md
```

Este reporte sirve para adjuntarlo junto al ZIP de entrega o usarlo como
checklist de revision local.
