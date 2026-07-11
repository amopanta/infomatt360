# Almacenamiento seguro multimedia (boveda S3/MinIO)

## Objetivo

Ofrecer un backend de almacenamiento alternativo al disco local para las
evidencias multimedia (fotos, audios, videos, firmas) que capturan los
gestores territoriales, respaldado en un bucket S3 o un contenedor MinIO
autoalojado.

## Lo que dice la especificacion original

**4.11. Modulo Almacenamiento Seguro Multimedia y Boveda S3** —
"Administra el flujo fisico de archivos pesados empleando la libreria
Boto3 conectada al contenedor privado de MinIO. Al recibir una imagen desde
la tablet, el motor comprime la fotografia convirtiendola dinamicamente al
formato de alta eficiencia WebP (reduciendo el peso del archivo hasta en un
70% sin perder nitidez forense), calcula un hash SHA-256 unico para blindar
el archivo contra alteraciones fisicas y lo deposita en la boveda cifrada,
retornando la ruta de acceso protegida interna para su almacenamiento en la
base de datos."

## Inactivo por defecto: el almacenamiento local sigue siendo la base

Igual que WAHA, Google Drive o la auditoria semantica con IA, este modulo
no reemplaza el flujo existente: mientras un proyecto no tenga un
`StorageProfile` con `provider="s3"` activo y marcado como
predeterminado (`is_default`), toda subida de evidencias sigue yendo a
disco local exactamente como antes (`file_service.upload_local`). Esto
se decide en tiempo real en `file_service.upload()`
(`backend/app/services/file_service.py`), que es ahora el punto de entrada
que usa `POST /api/v1/files/upload` en vez de llamar directo a
`upload_local`.

## Conectar una boveda S3/MinIO

`POST /api/v1/storage/s3/connect` (requiere acceso al proyecto):

```json
{
  "project_id": "...",
  "name": "S3 / MinIO",
  "bucket_name": "infomatt360-evidencias",
  "endpoint_url": "http://localhost:9000",
  "region": "us-east-1",
  "access_key_id": "...",
  "secret_access_key": "...",
  "is_default": true
}
```

`endpoint_url` es opcional: se deja vacio para AWS S3 real, o se apunta a
un contenedor MinIO (`http://host:9000`) para almacenamiento autoalojado.
Las credenciales (`access_key_id`, `secret_access_key`, `region`) se
cifran con Fernet (`encrypt_text`, la misma utilidad usada para tokens de
Google Drive y el secreto MFA) y se guardan en
`StorageProfile.credentials_json`; nunca se devuelven en las respuestas de
la API (`StorageProfileRead` no expone ese campo).

**Correccion de seguridad de paso**: `StorageProfileRead` exponia
literalmente `credentials_json` en texto plano en cualquier lectura de
perfiles de almacenamiento (`GET /api/v1/storage/project/{id}`), aunque
ese campo no lo usaba todavia ningun proveedor. Se removio del schema de
lectura y del endpoint generico de creacion; ahora solo el flujo dedicado
de S3 (`connect_profile`) escribe ese campo, siempre cifrado.

## Flujo de subida

1. `POST /api/v1/files/upload` recibe el archivo igual que siempre.
2. `file_service.upload()` busca un `StorageProfile` activo,
   `provider="s3"` y `is_default=true` para el proyecto. Si existe y tiene
   credenciales configuradas, delega en `upload_s3()`; si no, usa el flujo
   local sin cambios.
3. `s3_storage_service.upload_file()`:
   - Si el `mime_type` es una imagen convertible (`image/jpeg`,
     `image/png`, `image/bmp`, `image/tiff`), la decodifica con **Pillow**
     y la reescribe en formato **WebP** (calidad 82); si el contenido no
     es una imagen valida, se sube sin cambios (nunca falla la subida por
     esto).
   - Calcula el hash **SHA-256** sobre el contenido final (ya convertido),
     igual que hace `file_service.upload_local` para archivos locales.
   - Sube el objeto con `boto3` (`put_object`) a la clave
     `{project_id}/{sha256}-{nombre}` dentro del bucket configurado.
   - Si falla la subida (bucket inexistente, credenciales invalidas, MinIO
     caido), se traduce a `502 Bad Gateway` con un mensaje claro; el
     archivo nunca queda en un estado intermedio.

## Modelo

Reutiliza `StorageProfile` (`backend/app/models/storage.py`), que ya tenia
las columnas `bucket_name`, `endpoint_url` y `credentials_json` sin usar
desde que se penso el conector de Google Drive: no hizo falta una
migracion nueva para este modulo.

## Dependencias

- `boto3` (nuevo en `backend/requirements.txt`): cliente S3, compatible con
  MinIO via `endpoint_url`.
- `Pillow`: ya estaba instalado como dependencia de `qrcode[pil]` (Fase
  1.1), reutilizada aqui para la conversion a WebP.

## Pruebas

`backend/tests/test_s3_storage.py`: conecta un perfil S3 (con MinIO
simulado via un cliente `boto3` falso inyectado por `monkeypatch`), valida
que las credenciales nunca se devuelven en la respuesta, que una subida de
imagen real (PNG generado con Pillow) se convierte a WebP y su hash
coincide con el contenido subido, que sin perfil S3 conectado la subida
sigue yendo a local, y que un fallo del cliente S3 se traduce en
`502 Bad Gateway`.

## Como activarlo

1. Levanta un contenedor MinIO (`docker run -p 9000:9000 -p 9001:9001
   -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin
   minio/minio server /data --console-address ":9001"`) o usa un bucket
   S3 real de AWS.
2. Crea el bucket (ej. `infomatt360-evidencias`) desde la consola de MinIO
   o `aws s3 mb`.
3. `POST /api/v1/storage/s3/connect` con las credenciales del paso
   anterior.
4. A partir de ahi, toda subida de evidencias de ese proyecto va a la
   boveda S3/MinIO en vez de a disco local.

## Limites conocidos

- Un solo perfil S3 activo por proyecto puede actuar como destino por
  defecto (el mismo criterio de `is_default` que ya usaba el
  almacenamiento local).
- Sin editor visual en el frontend todavia: la conexion se hace via API
  (Swagger) o script, igual que el estado inicial de otros conectores
  (Google Drive, WAHA) antes de tener pantalla propia.
- No hay borrado logico ni migracion automatica de archivos ya subidos a
  disco local al conectar S3 despues; solo aplica a subidas futuras.
