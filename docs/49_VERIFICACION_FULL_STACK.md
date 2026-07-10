# Verificacion full stack local

## Objetivo

Levantar backend y frontend preview de forma temporal, validar health/readiness y
ejecutar el smoke test demo por API.

## Comando

Desde la raiz del proyecto:

```powershell
.\scripts\check-full-stack.cmd
```

## Requisitos

- `backend\.venv` existente.
- `backend\.env` preparado.
- Demo preparada con `.\scripts\prepare-demo.cmd`.
- `frontend\node_modules` instalado.
- Build frontend generado; si no existe, el script ejecuta `npm run build`.

## Que valida

- Backend `/health`.
- Backend `/api/v1/health/`.
- Backend `/api/v1/health/ready`.
- Frontend en `http://127.0.0.1:5173`.
- Login demo y rutas principales: sesion, dashboard, formularios, registros,
  reportes, mapas, revision, API keys, usuarios admin, mensajes, auditoria y
  metricas operativas.
