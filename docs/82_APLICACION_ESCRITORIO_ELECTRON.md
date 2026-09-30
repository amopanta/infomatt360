# Aplicación de escritorio InfoMatt360

El instalador Electron abre el mismo origen HTTPS del ERP publicado. Esto
permite usar la sesión, la API y los datos del VPS desde el escritorio y el
navegador. La sincronización de capturas pendientes usa una base SQLite local
mediante `sql.js` y el endpoint de lote de sesión, con claves de idempotencia.

La aplicación expone `window.desktopBridge` únicamente al origen de
InfoMatt360 y al servidor local de desarrollo. El puente ofrece la cola de
registros y funciones de impresión. La ventana bloquea navegación hacia otros
orígenes.

La prueba de dos vías, instalación y límites se detallan en
[desktop/README.md](../desktop/README.md). La sincronización en línea depende
del VPS. El primer inicio sin conexión y las capturas offline vinculadas a
participantes siguen pendientes.
