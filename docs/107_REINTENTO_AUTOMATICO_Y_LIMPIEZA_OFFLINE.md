# 107. Reintento automático y limpieza de sincronizados

## Qué cierra esto

El resto de la categoría B del documento de auditoría técnica externa de julio 2026 (ver docs/106 para SYNC-001/002/004, ya cerrados). Dos hallazgos que se dejaron aparte a propósito en esa sesión porque son cambios de *comportamiento automático*, no solo optimizaciones, y requerían decisiones de UX propias:

- **SYNC-003 (reintento automático en segundo plano):** antes, la sincronización offline solo ocurría si el usuario presionaba el botón, volvía la conexión (`window.addEventListener('online', ...)`), o algo más llamaba `syncNow()` explícitamente. El temporizador de 30s existente en `OfflineSyncStatus.tsx` solo refrescaba el *contador* visible de pendientes, nunca reintentaba nada.
- **SYNC-005 (limpieza automática de sincronizados):** los registros ya marcados `synced` en la cola local (IndexedDB en navegador/PWA, SQLite vía sql.js en escritorio) nunca se borraban — crecían indefinidamente.

**Alcance acordado con el usuario:**
- Backoff exponencial con techo: 30s → 1min → 2min → 4min, techo de 5 minutos; nunca "se rinde" del todo, sigue reintentando al ritmo del techo mientras haya pendientes.
- Condiciones de pausa: sin conexión (`navigator.onLine`) o pestaña/ventana en segundo plano (Page Visibility API).
- Retención de limpieza: 7 días.
- Disparo de limpieza: automática al final de cada sincronización exitosa **+** botón manual, siempre disponible, para forzarla antes de los 7 días.

## Por qué no se implementó la pausa por batería

El documento de auditoría original también pedía pausar el reintento cuando el dispositivo está en modo de ahorro de batería. Se investigó y **no es viable hoy**:

- La Battery Status API (`navigator.getBattery()`) fue removida de Chrome, Firefox y Safari por razones de privacidad (permitía huella digital del dispositivo). Ya no existe en ningún navegador moderno.
- Electron no expone el estado de batería del sistema operativo sin un módulo nativo adicional (no incluido en este proyecto).

En vez de simular o fingir este soporte, se documenta explícitamente como no viable. Las dos condiciones de pausa que sí son reales y soportadas (sin conexión, pestaña en segundo plano) se implementaron completas.

## Diseño

### SYNC-003 — `frontend/src/modules/offline/autoSyncService.ts` (nuevo)

Singleton a nivel de módulo, no un hook de React: `AppShell`/`OfflineSyncStatus` se vuelven a montar en cada navegación (este proyecto no tiene un layout persistente — cada pantalla envuelve su contenido en `<AppShell>` de nuevo) y el estado de backoff no debe reiniciarse por eso.

- `ensureStarted(apiBaseUrl)`: idempotente — si ya está corriendo, no hace nada. Dispara un primer intento de inmediato (no espera el intervalo base), para no hacer esperar a un usuario que abre la app con datos pendientes de una sesión anterior.
- Cada "tick": sin token de sesión (`currentAccessToken()` vacío) → no intenta nada y no cuenta como fallo (no crece el backoff por estar deslogueado). Sin conexión o pestaña oculta → salta el ciclo sin tocar el backoff, reprograma en 5s para reaccionar rápido cuando vuelva la condición. Si hay condiciones para sincronizar, llama al mismo `syncNow()` que usa el botón manual — una sola fuente de verdad, sin riesgo de que ambos caminos corran en paralelo.
- Resultado sin fallos → resetea el intervalo a 30s. Con fallos o error → dobla el intervalo hasta el techo de 5 minutos.
- Expone `getStatus()` y un evento `infomatt360:auto-sync-status-changed` para que la UI muestre el estado ("Pausado (sin conexión)", "Pausado (pestaña en segundo plano)") sin que el usuario tenga que adivinar por qué no está sincronizando.

`OfflineSyncStatus.tsx` llama `autoSyncService.ensureStarted()` en su `useEffect` (seguro de llamar en cada montaje por ser idempotente) y muestra la etiqueta de pausa cuando aplica.

### SYNC-005 — limpieza de sincronizados

- `indexedDbQueue.ts::purgeOldSynced(retentionDays)`: recorre el índice `status` en `'synced'` (mismo índice de docs/106), borra los que tengan `syncedAt` anterior al corte, devuelve cuántos borró. Nunca toca los `pending`.
- `desktop/src/offlineQueue.js::purgeOldSynced(queue, retentionDays)`: `DELETE FROM queued_records WHERE status = 'synced' AND synced_at < ?`, persiste, devuelve el número de filas afectadas.
- `desktop/src/preload.js` + `desktop/src/main.js`: nuevo canal IPC `desktop:purge-old-synced`, mismo patrón que los canales existentes.
- `frontend/src/modules/desktop/desktopBridge.ts`: `purgeOldSynced` agregado al tipo `DesktopBridge`.
- `offlineSync.ts::purgeOldSynced(retentionDays = 7)`: fachada que branchea `isDesktopApp()` igual que el resto de la cola. Se llama automáticamente al final de `syncNow()` (después de procesar todos los grupos, antes del evento de cambio de cola), y queda exportada para el botón manual.

### El botón manual queda siempre disponible, no solo cuando hay pendientes

Durante la verificación en vivo se detectó que `OfflineSyncStatus.tsx` ocultaba el widget completo (`if (pending === 0 && !message) return null`) cuando no había nada pendiente — lo que dejaba el botón "Limpiar sincronizados antiguos" inalcanzable justo en el escenario para el que existe: sin capturas pendientes, pero con registros sincronizados hace más de una semana que el usuario quiere borrar ya. Como la purga automática solo corre dentro de un `syncNow()` exitoso, si no hay nada pendiente desde hace días esa purga automática tampoco se dispara nunca. Se corrigió para que el botón de limpieza se muestre siempre; el botón "Sincronizar pendientes (N)" sigue apareciendo solo cuando `N > 0`.

## Pruebas

- `frontend/src/modules/offline/autoSyncService.test.ts` (nuevo, 7 pruebas, `vi.useFakeTimers()`): no sincroniza sin sesión y no lo cuenta como fallo; se pausa sin red; se pausa con pestaña oculta; no llama a `syncNow` sin pendientes; sincroniza y resetea el intervalo si no hubo fallos; el intervalo crece con backoff exponencial hasta el techo de 5 minutos cuando hay fallos; `ensureStarted` es idempotente (llamarlo dos veces no dispara dos ciclos).
- `frontend/src/modules/offline/indexedDbQueue.test.ts` (2 pruebas nuevas): `purgeOldSynced` borra los sincronizados vencidos y conserva los recientes y los pendientes; no borra nada si ninguno supera la retención.
- `desktop/src/offlineQueue.test.js` (2 pruebas nuevas): mismas aserciones que el lado navegador, adaptadas a Node/sql.js.

## Verificación en vivo

Contra el backend y frontend reales de la demo, con navegador real y sesión de `admin@infomatt360.demo`: se escribieron 3 registros de prueba directo en la IndexedDB real (1 `pending`, 1 `synced` con `syncedAt` de hace 10 días, 1 `synced` de hace 2 días) y se recargó la aplicación.

Se confirmó que la pestaña del navegador embebido reporta `document.visibilityState = 'hidden'` (comportamiento normal de una pestaña que no tiene el foco real del sistema operativo) — y el servicio automático reaccionó correctamente mostrando "Pausado (pestaña en segundo plano)" en la interfaz, **sin** intentar sincronizar, confirmando en vivo la condición de pausa. Al forzar `visibilityState` a `'visible'` y disparar `visibilitychange` (simulando que el usuario trae la pestaña al frente, ya que el entorno de la herramienta de navegador no permite dar foco real del SO), el siguiente ciclo programado (dentro de los 5s de re-chequeo de pausa) sincronizó el registro pendiente **sin ninguna acción manual del usuario**: `POST /runtime/session/bulk-save` real con 200 OK, el registro quedó `synced` en IndexedDB, y — como consecuencia directa de la purga automática al final de `syncNow()` — el registro `synced` de hace 10 días desapareció de la cola mientras el de hace 2 días se conservó intacto. Esto confirmó SYNC-003 y la mitad automática de SYNC-005 en una sola pasada.

Para el botón manual: con la cola en 0 pendientes, se confirmó que "Limpiar sincronizados antiguos" seguía visible (tras el arreglo descrito arriba) y, al hacer clic sin nada vencido, mostró "No había registros sincronizados con más de 7 días."; se insertó un registro `synced` adicional de hace 8 días y, al hacer clic de nuevo, mostró "1 registro(s) sincronizado(s) antiguo(s) eliminado(s) del dispositivo." y lo eliminó.

Se confirmó en la base de datos real (`infomatt360_demo.db`) que el registro creado por la sincronización automática (`AutoSyncTest`) y el `BulkImportJob` de idempotencia asociado quedaron creados correctamente vía el endpoint real. Todos los datos de prueba (los registros de IndexedDB, el `RuntimeRecord` real y sus valores, y el `BulkImportJob`) se eliminaron al finalizar; `backend/.env` y `frontend/.env.local` se revirtieron a su estado original.
