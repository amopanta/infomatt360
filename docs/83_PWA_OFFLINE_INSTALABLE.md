# PWA instalable y offline

## Objetivo

Que el mismo frontend web se pueda instalar como aplicacion (movil o
escritorio) desde el navegador, siga funcionando sin conexion, y comparta
la misma logica de cola/sincronizacion offline que la app de escritorio
Electron (ver [82_APLICACION_ESCRITORIO_ELECTRON.md](82_APLICACION_ESCRITORIO_ELECTRON.md)).

## Instalabilidad

`vite-plugin-pwa` (`frontend/vite.config.ts`) genera el manifest
(`manifest.webmanifest`) y el service worker (`sw.js`, modo `generateSW` de
Workbox) en el build de produccion. El service worker **solo se activa en
builds de produccion** (`npm run build` + `vite preview` o el despliegue
real); no en `npm run dev`.

Cacheo:

- App shell (JS/CSS/HTML, iconos): precacheado por Workbox para que la app
  cargue incluso sin red.
- Llamadas a `/api/`: `NetworkFirst` (intenta red primero, timeout 5s, cae
  al cache solo si no hay conexion) — evita servir siempre datos viejos
  cuando si hay red.

El manifest es estatico y no refleja el branding dinamico por organizacion
(ver [72_MARCA_BLANCA_DINAMICA.md](72_MARCA_BLANCA_DINAMICA.md)); queda con
la identidad generica de la plataforma.

## Cola offline compartida: `offlineSync.ts`

`frontend/src/modules/offline/offlineSync.ts` es la fachada unica que usan
tanto el boton de sincronizar como el guardado de Runtime, sin que el resto
de la app sepa cual de las dos implementaciones esta activa:

- Dentro de Electron (`isDesktopApp()` verdadero): delega a
  `window.desktopBridge` (sql.js, ver doc 82).
- En navegador/PWA normal: delega a
  `frontend/src/modules/offline/indexedDbQueue.ts`, que usa la API nativa
  de IndexedDB (sin dependencias adicionales) con la misma forma de datos
  (`enqueue`/`listPending`/`countPending`/`markSynced`/`markFailed`).

Ambas implementaciones sincronizan contra el mismo endpoint
(`POST /api/v1/runtime/save`, no `/runtime/bulk/save` — ver la nota de
seguridad en la doc 82, el mismo riesgo de idempotencia aplica aqui).

## Guardado offline-first en Runtime

`frontend/src/modules/runtime/RuntimeApp.tsx`: cuando `save()` falla por
`TypeError` (fallo de red real, no un error de validacion HTTP del
servidor), encola el registro con `enqueueRecord()` en vez de perder la
captura.

## UI de sincronizacion

`frontend/src/components/OfflineSyncStatus.tsx` (antes
`DesktopSyncStatus.tsx`, generalizado para ambos entornos): boton
"Sincronizar pendientes (N)", oculto cuando no hay pendientes ni mensaje.
Se actualiza en tiempo real via el evento `infomatt360:offline-queue-changed`
(disparado por `offlineSync.ts` en cada encolado/sincronizacion, sin
esperar el poll periodico de 30s) y auto-sincroniza al detectar el evento
`online` del navegador.

## Escaneo de QR de enrolamiento por camara

`frontend/src/modules/enrollment/EnrollScanApp.tsx` (ruta publica
`/enroll`): si la URL trae `?token=...` valida directo; si no, abre la
camara (`getUserMedia({ video: { facingMode: 'environment' } })`) y
decodifica cada cuadro con `jsqr` (bucle `requestAnimationFrame` + canvas)
hasta encontrar un QR valido. Ver
[74_QR_ENROLAMIENTO_GESTOR.md](74_QR_ENROLAMIENTO_GESTOR.md) para el
backend de generacion/validacion del token.

## Limites conocidos

- Riesgo de idempotencia de `/runtime/save` (ver doc 82) aplica igual aqui.
- El manifest no es dinamico por organizacion (ver seccion de
  instalabilidad arriba).
- El service worker no se prueba en `npm run dev`; verificar siempre con un
  build de produccion antes de dar por buena una prueba de PWA.
