# Aplicacion de escritorio (Electron)

## Objetivo

Empaquetar el mismo frontend web (`frontend/`) como aplicacion de
escritorio instalable, con captura de datos sin conexion y sincronizacion
por lotes, sin mantener un codebase nativo separado. Ver el detalle
operativo completo en [desktop/README.md](../desktop/README.md); este
documento resume el diseno para el indice general de `docs/`.

## Como carga el frontend (y por que no usa `file://`)

Bajo `file://`, las rutas absolutas que genera el build de Vite
(`/assets/...`) resuelven contra la raiz del sistema de archivos, no contra
la carpeta del `index.html` — la ventana quedaba en blanco. En vez de
forzar rutas relativas (que rompe la recarga de rutas profundas de la SPA
en el despliegue web normal), `desktop/src/main.js` levanta un servidor
HTTP local minimo (`desktop/src/staticServer.js`, Node `http` puro, con
fallback de SPA) y carga el frontend via
`http://127.0.0.1:<puerto>/`. Las mismas rutas absolutas que usa el
despliegue web funcionan igual aqui, incluyendo rutas profundas como
`/runtime/xyz`.

## Cola offline: sql.js, no better-sqlite3

`better-sqlite3` es un modulo nativo que exige recompilarse contra el ABI
de Electron con Visual Studio Build Tools — no siempre disponible en el
equipo de desarrollo. `desktop/src/offlineQueue.js` usa `sql.js` (SQLite
compilado a WebAssembly): corre igual dentro y fuera de Electron sin paso
de compilacion, a cambio de tener que persistir el archivo a mano
(`db.export()` + `fs.writeFileSync`) despues de cada escritura.

## Puente hacia el frontend

`desktop/src/preload.js` expone `window.desktopBridge` via
`contextBridge` (con `contextIsolation: true`, `nodeIntegration: false` —
sin acceso directo a Node desde el renderer):

- `enqueueRecord({ projectId, templateId, values })`
- `getPendingCount()`
- `syncNow({ apiBaseUrl, accessToken })`

El frontend web (compartido con la version navegador/PWA) usa la misma
fachada `offlineSync.ts` para ambos casos — ver
[83_PWA_OFFLINE_INSTALABLE.md](83_PWA_OFFLINE_INSTALABLE.md).

## Sincronizacion: `/runtime/save`, no `/runtime/bulk/save`

`syncNow` reenvia los pendientes contra `POST /api/v1/runtime/save` (sesion
normal de usuario), no contra `/runtime/bulk/save` (ese exige API key para
integraciones externas y devuelve `401` con una sesion de usuario normal).

**Riesgo conocido, no resuelto en esta version**: `/runtime/save` no tiene
`idempotency_key`. Si la respuesta del servidor se pierde en la red justo
despues de guardar el registro, un reintento de sincronizacion podria
duplicarlo. El anti-duplicidad por hash de contenido
([77_ANTI_DUPLICIDAD.md](77_ANTI_DUPLICIDAD.md)) actua como red de
seguridad adicional (marca posible duplicado), pero no lo previene.

## Empaquetado

`npm run build:win` / `build:mac` / `build:linux` (electron-builder) copian
el build de `frontend/dist` como recurso empaquetado
(`extraResources` en `desktop/package.json`) y generan el instalador en
`desktop/release/`.

## Limites conocidos

- Ver el riesgo de idempotencia arriba.
- No hay actualizaciones automaticas (auto-update) configuradas todavia.
