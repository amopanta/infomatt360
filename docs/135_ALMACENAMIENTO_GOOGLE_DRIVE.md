# Google Drive como destino de evidencias

## Configuración

El servidor necesita `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` y `GOOGLE_OAUTH_REDIRECT_URI`. El URI de redirección debe apuntar al callback `/api/v1/storage/oauth/gdrive/callback` y estar autorizado en el cliente OAuth de Google. La cuenta que conecta Drive debe tener permiso `storage.manage` en el proyecto.

En **Administración → Almacenamiento → Google Drive**, conectar la cuenta. Al terminar la autorización, actualizar la lista y pulsar **Usar para nuevas subidas** en el destino Google Drive. Solo un destino por proyecto queda marcado como predeterminado. Las evidencias anteriores permanecen en su proveedor original y se pueden descargar desde ese proveedor.

Las subidas de hasta 5 MB usan el protocolo `multipart/related` de Google Drive. Los archivos mayores usan una sesión resumible. El backend registra `gdrive://<perfil>/<archivo>` y recupera el archivo por la API de Drive. Los tokens OAuth se guardan cifrados en la base de datos y se actualizan cuando vencen. Si falla Drive, la subida devuelve error: no se cambia silenciosamente al disco local.

## Límites de seguridad

Esta integración cubre evidencias generales. **No habilita la captura de huellas de participantes**: para datos biométricos se necesita el flujo separado de [captura de huella](134_CAPTURA_HUELLA_PARTICIPANTE.md), cifrado del contenido antes de subirlo, permisos específicos, consentimiento y auditoría. Seleccionar Drive como destino no sustituye esos controles.

## Comprobación

Verificar el destino activo en la tabla, subir una evidencia de prueba y descargarla. Confirmar en la ficha del archivo que `storage_provider` es `gdrive` y que los archivos previos mantienen su proveedor. Si falla la conexión OAuth, comprobar la configuración del cliente en el VPS y el URI de redirección sin exponer secretos.

