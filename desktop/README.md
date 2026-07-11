# InfoMatt360 Desktop

Shell de Electron que envuelve el mismo frontend web (`../frontend`), agregando
una cola local offline para capturas sin conexion.

## Por que Electron + sql.js (no better-sqlite3)

`better-sqlite3` es un modulo nativo: debe recompilarse contra el ABI de
Electron con Visual Studio Build Tools instalado. En un equipo de desarrollo
sin esas herramientas, la recompilacion falla. `sql.js` (SQLite compilado a
WebAssembly) evita ese problema por completo, a cambio de tener que llamar
`db.export()` y escribirlo a disco despues de cada escritura (ver
`src/offlineQueue.js`).

## Desarrollo

```powershell
# 1. Backend y frontend corriendo (ver README raiz del proyecto)
npm install
npm run dev
```

Por defecto carga el build de produccion del frontend
(`../frontend/dist/index.html`, hay que correr `npm run build` en `frontend/`
primero). Para apuntar al servidor de desarrollo de Vite en su lugar:

```powershell
$env:ELECTRON_START_URL = "http://127.0.0.1:5173"
npm run dev
```

## Pruebas

La cola offline (`src/offlineQueue.js`) es codigo Node puro, sin dependencia
de Electron, y tiene pruebas con el test runner nativo de Node:

```powershell
npm test
```

## Cola offline

`window.desktopBridge` (expuesto via `src/preload.js`) da acceso desde el
frontend a:

- `enqueueRecord({ projectId, templateId, values })` - guarda una captura
  localmente. `values` debe ser `[{ field_name, field_value_json }, ...]`,
  el mismo formato que usa `POST /api/v1/runtime/save`.
- `getPendingCount()` - cuantos registros faltan por sincronizar.
- `syncNow({ apiBaseUrl, accessToken })` - reenvia los pendientes contra
  `POST /api/v1/runtime/save` (el mismo endpoint que usa el guardado en
  linea, con la sesion normal del usuario). **No** usa
  `POST /api/v1/runtime/bulk/save`: ese endpoint exige autenticacion por API
  key (`require_api_key_permission`) para integraciones externas, no sesion
  de usuario -- se probo primero con el backend real y devolvia 401 "API key
  requerida".

**Riesgo conocido, no resuelto en esta version**: `/runtime/save` no tiene
`idempotency_key`. Si la respuesta del servidor se pierde en la red despues
de que el registro ya se guardo (ej. se corta la conexion justo despues del
200 OK), un reintento de sincronizacion crearia un registro duplicado. La
cola local si evita reintentos de registros ya marcados `synced`, pero no
puede distinguir ese caso especifico (exito silencioso) de un fallo real.
Mitigacion futura: agregar idempotencia a `/runtime/save` en el backend, o
usar el anti-duplicidad por hash de contenido que ya existe en
`runtime_record_service.py` (Fase 1.4) como red de seguridad adicional.

**UI conectada**: el boton "Sincronizar pendientes (N)" ya esta en la barra
superior (`frontend/src/components/DesktopSyncStatus.tsx`, visible solo
cuando `window.desktopBridge` existe) y el guardado de Runtime
(`frontend/src/modules/runtime/RuntimeApp.tsx`) encola automaticamente en
vez de perder la captura cuando `fetch` falla por falta de red (`TypeError`,
no un error HTTP real del servidor).

## Empaquetado

```powershell
cd ../frontend; npm run build
cd ../desktop
npm run build:win   # o build:mac / build:linux
```

Genera el instalador en `desktop/release/`. El build del frontend se copia
como recurso empaquetado (`extraResources` en `package.json`).
