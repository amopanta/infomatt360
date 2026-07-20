# 115. Impresión nativa de actas desde el cliente de escritorio

## Qué cierra esto

El ítem #10 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md`: "Selección de impresora e impresión masiva/individual desde el cliente de escritorio (§15)". Antes de este cambio, el shell de Electron (`desktop/src/*.js`) solo servía el frontend estático y manejaba la cola offline — no había ninguna integración de impresión nativa en ningún lugar del repo, ni siquiera un `window.print()` de respaldo.

**Alcance:** el único contenido imprimible que existe en el sistema son las actas PDF (individual y en lote, docs/109/110) — este ítem le da al cliente Electron la capacidad de imprimir esos mismos PDF ya generados usando el selector de impresora nativo del sistema operativo, en vez del flujo actual de "descargar y luego imprimir desde el visor de PDF". No se construyó una capacidad genérica de "imprimir cualquier pantalla".

**Decisión de diseño:** sin fallback de impresión en el navegador. La selección de impresora nativa/silenciosa no tiene equivalente real en navegador (a diferencia de la cola offline, que sí tiene un equivalente real vía IndexedDB) — el navegador ya tiene su propio flujo hoy (descargar y abrir con el visor de PDF del sistema). El propio texto del ítem de la auditoría dice explícitamente "cliente de escritorio".

## Diseño

### `desktop/src/printing.js`

Nuevo módulo, mismo estilo que `offlineQueue.js` (CommonJS, comentarios en español, sin logging a consola). Usa las APIs reales de Electron 43 (`webContents.getPrintersAsync`/`webContents.print`, ninguna de las variantes síncronas/deprecadas). Como `webContents.print()` imprime lo que ya está cargado en ese `webContents` (no bytes de PDF directos), cada PDF se escribe a un archivo temporal (`app.getPath("temp")`) y se carga vía `pathToFileURL(...)` en una `BrowserWindow` oculta (Chromium trae su propio visor de PDF) antes de imprimir.

Para el lote (`printBatchZip`), se usa `fflate` (`unzipSync`, pura JS sin bindings nativos — mismo criterio que ya llevó a elegir `sql.js` sobre `better-sqlite3` en este proyecto: no hay toolchain de rebuild contra el ABI de Electron) para desempaquetar el ZIP de actas, se reutiliza una sola ventana oculta para todas las impresiones del lote (en vez de crear hasta 200, el tope de `settings.acta_batch_max_records`), y un fallo por ítem no aborta el lote — el resultado final (`{printed, failed, errors}`) sigue el mismo espíritu que `manifest.csv` del backend (`acta_service.render_pdf_batch`, docs/110).

**Lógica pura, testeable con `node --test`:** `extractPdfEntries` (ignora `manifest.csv`, ordena por nombre) y `summarizePrintResults`. **No testeable fuera de un proceso Electron real:** `listPrinters`, `printLoadedPdf`, `printPdfBuffer`, `printBatchZip` — verificadas por revisión de código y por la verificación en vivo descrita abajo, mismo criterio de honestidad ya aplicado en docs/113 (Postgres/PostGIS real) y docs/114 (Tableau Desktop real).

### IPC y frontend

3 canales nuevos siguiendo la convención ya establecida `desktop:<verbo-sustantivo>` (`desktop:list-printers`, `desktop:print-document`, `desktop:print-batch`), expuestos en `desktop/src/preload.js` como 3 métodos nuevos de `window.desktopBridge`. `frontend/src/modules/desktop/desktopBridge.ts` gana los tipos correspondientes (`PrinterInfo`, `DesktopPrintResult`, `DesktopBatchPrintResult`).

`frontend/src/modules/acta/api.ts` extrae la lógica de fetch+auth+error ya duplicada en `renderActaFromRecord`/`renderActaBatch` (`fetchActaBinary`/`downloadBlob`, sin cambiar su comportamiento) y agrega `printActaFromRecord`/`printActaBatch`: mismo fetch que las funciones de descarga, pero via `arrayBuffer()` en vez de disparar una descarga, entregando los bytes a `window.desktopBridge`.

Un componente compartido nuevo, `frontend/src/modules/desktop/PrinterPicker.tsx` (selector de impresora + copias), se usa en ambos puntos de integración: `GenerateActaPanel` (registro individual) y `BulkActaBar` (lote), ambos en `frontend/src/modules/records/RecordsApp.tsx`, dentro de un bloque `isDesktopApp()` junto a los botones de generación/descarga ya existentes (no los reemplaza). El resultado del lote se formatea con una función pura nueva, `formatBatchPrintMessage` (`frontend/src/modules/desktop/printSummary.ts`).

## Pruebas

`desktop/src/printing.test.js` (7 pruebas nuevas, Node's test runner, ZIPs de prueba construidos con `fflate.zipSync`): `extractPdfEntries` ignora `manifest.csv` y ordena por nombre, ignora entradas que no terminan en `.pdf`, ZIP sin PDFs da arreglo vacío; `summarizePrintResults` cubre todos exitosos, fallas parciales con motivo, lote vacío, y motivo por defecto cuando `failureReason` viene vacío.

`frontend/src/modules/desktop/printSummary.test.ts` (3 pruebas nuevas, vitest): sin fallas, con fallas parciales, lote vacío.

Suite completa tras el cambio: `desktop` 17/17 (`node --test`, 10 previos + 7 nuevos), frontend 101/101 (98 previos + 3 nuevos), `tsc --noEmit` y `npm run build` limpios. `node -e "require('./src/printing.js')"` confirma que el módulo carga limpio bajo Node plano (sin proceso Electron real), como se esperaba dado que `require("electron")` fuera de Electron devuelve un string en vez del objeto de API real.

**Límite explícito, no fingido:** no hay impresora real ni forma de lanzar/controlar un proceso Electron real desde este entorno de desarrollo — las funciones que llaman a la API real de Electron (`getPrintersAsync`, `webContents.print`, crear `BrowserWindow`) quedan cubiertas solo por revisión de código, pendientes de una prueba manual futura en una máquina Windows real con una impresora real (o "Microsoft Print to PDF").

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`), usando el navegador de esta sesión (no Electron real) con un `window.desktopBridge` **falso** inyectado por consola, para validar todo el pipeline excepto la llamada nativa final:

- Se creó una plantilla de acta de prueba real ("Acta de prueba impresion") para el formulario `demo-template-characterization` (necesaria porque el proyecto demo no tenía ninguna plantilla de acta activa en el momento de esta verificación).
- Con el bridge falso instalado, el selector de impresora y el botón "Imprimir" aparecieron correctamente en `GenerateActaPanel` (registro individual), mostrando "Impresora de prueba (predeterminada)".
- Clic en "Imprimir" sobre un registro real → mensaje "Acta enviada a impresión."; `window.__printCalls[0]` confirmó `byteLength: 2110` (bytes reales del PDF generado por el backend), `deviceName: "FAKE01"`, `copies: 1`.
- Con 2 registros seleccionados, "Imprimir lote" apareció en `BulkActaBar` junto al mismo selector de impresora. Clic → mensaje "2 acta(s) impresa(s)." (formateado con `formatBatchPrintMessage`); `window.__printCalls[1]` confirmó `byteLength: 2787` (bytes reales del ZIP de actas generado por el backend), mismo `deviceName`/`copies`.
- Esto valida todo el pipeline (gating de UI por `isDesktopApp()`, listado de impresoras, secuencia fetch real→entrega al bridge, forma correcta de los argumentos) salvo la llamada nativa final dentro de `desktop/src/printing.js` (escritura del temporal, creación de `BrowserWindow` oculta, `loadURL`/`webContents.print`) — eso queda pendiente de una prueba manual futura en una máquina Windows real.
- Se eliminó la plantilla de acta de prueba directo en la base de datos demo (no existe endpoint DELETE); se revirtieron `backend/.env` (línea `CORS_ALLOWED_ORIGINS`) y se eliminó `frontend/.env.local`.

## Lo que queda fuera de esta sesión

Con esto se cierran los 10 primeros ítems de docs/96 (#1-#10). Queda #11 (bandeja de correo externa vía IMAP).
