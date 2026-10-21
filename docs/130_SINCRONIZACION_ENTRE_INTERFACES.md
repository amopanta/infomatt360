# Sincronización entre navegador, escritorio y servidor

> La app móvil oficial tiene su propio modelo sin conexión (captura nueva sin red, correcciones diferenciales): ver el repositorio `infomatt360-mobile` (`docs/ARQUITECTURA.md`) y [docs/142](142_VALIDACION_FUNCIONALIDADES_DOCS141.md). Este documento cubre web y escritorio.

## Flujo de captura

Una respuesta se valida y se envía con el identificador del participante. Si falla el transporte, la aplicación conserva la respuesta en la cola local del navegador (IndexedDB) o del escritorio (SQLite). El usuario ve un mensaje de guardado local. Un error HTTP de validación o permisos se muestra para corregirse y no entra en la cola.

Cada lote pendiente se envía a `/runtime/session/bulk-save` con una clave de idempotencia estable. La cola conserva el participante asociado; los registros anteriores a esta mejora, que no tenían esa relación, siguen siendo legibles. Solo se marca sincronizado cada elemento que el servidor confirma como creado. Una respuesta parcial o inválida deja los demás elementos pendientes y registra el error para el siguiente intento.

La sincronización automática reintenta con espera progresiva mientras haya conexión y una sesión activa. El panel de sincronización muestra los pendientes. El escritorio escribe su archivo de cola mediante un archivo temporal y renombrado para reducir el riesgo de daño si la aplicación se interrumpe durante la escritura.

## Alcance y verificación

Las pruebas automáticas cubren el envío del participante y respuestas parciales en navegador y escritorio, además de los casos previos de red, error HTTP, lotes y persistencia. La compilación del frontend confirma que el formulario usa la misma cola. Para una prueba de campo, abrir un formulario asignado con conexión, desconectar la red, guardar una respuesta, comprobar el contador pendiente, reconectar y verificar el registro y su participante en el servidor.

En el navegador web, la carga inicial de formularios, participantes y grupos Pull todavía requiere conexión; el escritorio sí trabaja sin red (sección siguiente). La cola protege respuestas de formularios ya abiertos y habilitados que pierden la conexión durante el diligenciamiento. No debe interpretarse como disponibilidad completa de todos los formularios desde un arranque sin red.

## Escritorio sin conexión

Actualizado: 2026-10-19. Solo en la app de escritorio (Electron); en un
navegador compartido no se guardan datos de participantes en el equipo.

1. **Con conexión**, en *Llenar formularios*, el panel **Trabajo sin conexión**
   baja el paquete del proyecto: formularios asignados y abiertos, su
   definición, participantes y respuestas previas (hasta 300 participantes,
   como la tablet). Se renueva solo si tiene más de 30 minutos. Ahí mismo el
   gestor crea un **PIN de 4 a 8 dígitos**.
2. **Sin conexión**, al abrir la app se pide el PIN en vez de la contraseña.
   La copia de la sesión vence a los 7 días sin conectarse; cinco PIN
   erróneos bloquean cinco minutos; cerrar sesión borra la copia. El PIN se
   guarda derivado con PBKDF2-SHA256, nunca en claro.
3. El gestor abre formularios y participantes desde la copia local
   (`frontend/src/modules/offline/offlineCache.ts`, por usuario) y guarda en
   la cola local. La actividad queda marcada como aplicada para no capturar
   dos veces al mismo participante antes de sincronizar.
4. **Al volver la red**, la app renueva la sesión sola (cada 30 s o con el
   evento `online`) y envía la cola. Si la sesión venció, pide iniciar sesión
   sin perder lo pendiente.

Cada registro en cola guarda quién lo capturó (`user_id`): si otra persona
inicia sesión en el mismo equipo, solo envía los suyos (y los antiguos sin
dueño).

**Prueba real (2026-10-19):** app de escritorio con el servidor local
apagado. Entró con PIN, abrió el formulario "h04" de una participante desde
la copia, guardó la respuesta en la cola y bloqueó una segunda captura. Al
encender el servidor reconectó sola y sincronizó en 42 s: un único registro,
autor la gestora, asignación en "completed".

**Límites:**
- Los formularios con verificación de dispositivo (huella) o `pulldata` en
  línea necesitan conexión para enviarse.
- Registrar un participante nuevo y cambiar su teléfono requieren conexión.
- Las correcciones de registros devueltos se hacen en línea en el
  escritorio; la corrección sin red está en la tablet.
- El primer arranque de la app instalada necesita conexión para que el
  service worker guarde la aplicación.
