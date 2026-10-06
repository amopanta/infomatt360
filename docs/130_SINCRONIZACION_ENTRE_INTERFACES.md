# Sincronización entre navegador, escritorio y servidor

## Flujo de captura

Una respuesta se valida y se envía con el identificador del participante. Si falla el transporte, la aplicación conserva la respuesta en la cola local del navegador (IndexedDB) o del escritorio (SQLite). El usuario ve un mensaje de guardado local. Un error HTTP de validación o permisos se muestra para corregirse y no entra en la cola.

Cada lote pendiente se envía a `/runtime/session/bulk-save` con una clave de idempotencia estable. La cola conserva el participante asociado; los registros anteriores a esta mejora, que no tenían esa relación, siguen siendo legibles. Solo se marca sincronizado cada elemento que el servidor confirma como creado. Una respuesta parcial o inválida deja los demás elementos pendientes y registra el error para el siguiente intento.

La sincronización automática reintenta con espera progresiva mientras haya conexión y una sesión activa. El panel de sincronización muestra los pendientes. El escritorio escribe su archivo de cola mediante un archivo temporal y renombrado para reducir el riesgo de daño si la aplicación se interrumpe durante la escritura.

## Alcance y verificación

Las pruebas automáticas cubren el envío del participante y respuestas parciales en navegador y escritorio, además de los casos previos de red, error HTTP, lotes y persistencia. La compilación del frontend confirma que el formulario usa la misma cola. Para una prueba de campo, abrir un formulario asignado con conexión, desconectar la red, guardar una respuesta, comprobar el contador pendiente, reconectar y verificar el registro y su participante en el servidor.

La carga inicial de formularios, participantes y grupos Pull todavía requiere conexión. La cola protege respuestas de formularios ya abiertos y habilitados que pierden la conexión durante el diligenciamiento. No debe interpretarse como disponibilidad completa de todos los formularios desde un arranque sin red.
