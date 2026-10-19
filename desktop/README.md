# InfoMatt360 Escritorio

Aplicación Electron para Windows que abre el ERP publicado en
`https://infomatt360.tecnomatt.com/`. Usa la misma cuenta, API y base de datos
que la web. Los cambios guardados en línea se ven en ambos sentidos al volver
a consultar los datos.

## Instalación y prueba de dos vías

1. Instalar `InfoMatt360 Setup 0.1.0.exe` en Windows y abrir InfoMatt360.
2. Iniciar sesión con una cuenta de pruebas.
3. Crear o editar un registro de prueba en el escritorio y comprobarlo en el navegador.
4. Cambiar ese registro desde el navegador y recargarlo en el escritorio.
5. Para la cola local, capturar sin red en un formulario que admita capturas
   offline, reconectar y pulsar **Sincronizar pendientes**. Confirmar que el
   registro aparezca una sola vez en el servidor.

La cola local usa `sql.js` y envía lotes a
`POST /api/v1/runtime/session/bulk-save` con claves de idempotencia. Las
pruebas están en `src/offlineQueue.test.js`.

## Límites actuales

- El primer inicio requiere conexión al VPS. Después, la app entra **sin
  red con un PIN** y captura con el paquete descargado en *Llenar
  formularios* (ver `docs/130`, sección "Escritorio sin conexión").
- Registrar participantes nuevos, la verificación de huella y `pulldata`
  en línea siguen necesitando conexión.
- Los servicios de correo, mensajería y otras integraciones externas dependen
  de las credenciales y la configuración del VPS.
- El instalador no incluye actualizaciones automáticas. Para una nueva versión
  se genera y distribuye otro instalador.

## Desarrollo

`ELECTRON_START_URL` permite apuntar a Vite. Sin esa variable, el modo de
desarrollo sirve `../frontend/dist` desde un servidor HTTP local. La versión
empaquetada siempre usa el origen publicado, salvo que se configure
`INFOMATT360_DESKTOP_URL` antes de abrirla. El puente local solo se expone al
origen publicado o al servidor local de desarrollo.

```powershell
pnpm install
node --test src/*.test.js
pnpm run build:win
```
