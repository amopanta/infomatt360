# 122. Pantalla de Marca: subir el logo de la organización

## Qué cierra esto

El primer hallazgo de las pruebas funcionales del usuario contra el stack local (2026-07-25): el bloque "Logo" del constructor de actas (docs/109) decía "automático" pero **no existía ninguna forma de cargar ese logo desde la interfaz**. El backend tenía el endpoint de branding (`PUT /organizations/{id}/branding`) desde el inicio del modelo multi-tenant, pero ningún lugar del frontend lo llamaba y el instalador tampoco lo pedía — la funcionalidad prometía algo que la interfaz no dejaba hacer.

Hueco adicional encontrado al diseñar esto: el proyecto demo (y cualquier proyecto existente) tenía `organization_id` vacío y **no existía endpoint para vincularlo** — limitación ya documentada honestamente en la verificación de docs/109. Sin ese enlace, el logo jamás aparecería en las actas aunque se pudiera subir. Se cerró en el mismo cambio.

## Diseño

### Subida real de archivo, no URL a mano

`logo_url` siempre fue una URL (`String(500)`). Pedirle al usuario que consiga una URL pública para su logo no es una solución real, así que:

- **`POST /organizations/{id}/branding/logo`** (multipart): valida tipo (PNG/JPEG/WebP — SVG excluido a propósito, puede contener scripts si se abre directo) y tamaño (≤2MB), guarda el archivo en `{UPLOAD_DIRECTORY}/branding/{org_id}.{ext}` (un solo archivo por organización, reemplaza el anterior incluso al cambiar de formato) y deja `logo_url` apuntando al endpoint público nuevo, con `?v={timestamp}` para invalidar caché de navegadores. **Solo toca `logo_url`** — a diferencia de `PUT /branding` (que pisa todos los campos), los colores y eslogan ya configurados se preservan.
- **`GET /public/branding-logo/{organization_id}`**: sirve los bytes con el content-type correcto. Público por el mismo criterio que `/public/branding`: el logo se muestra antes de iniciar sesión (login, PWA) y no revela nada sensible.
- El directorio vive dentro de `UPLOAD_DIRECTORY`, que en el compose productivo es el volumen `uploads_data` compartido entre `backend-1`/`backend-2`/workers — el logo subido por una réplica es visible para la otra sin nada adicional.

### El PDF lee el archivo local, no se hace fetch a sí mismo

`acta_service` ahora detecta cuando `logo_url` apunta al endpoint propio (`/public/branding-logo/`) y le pasa a xhtml2pdf la **ruta local del archivo** en vez de la URL. Sin esto, el backend tendría que hacerse un fetch HTTP a su propio nombre público desde dentro del contenedor — frágil (hairpin NAT, TLS interno) y lento. URLs externas (un logo hosteado en un CDN, el caso que ya cubría el test de docs/109) siguen incrustándose por URL, sin cambio.

### `PATCH /identity/projects/{id}`: el enlace proyecto→organización por fin es editable

Permiso `organizations.manage` (el mismo que crear proyectos), valida que la organización exista, acepta `null` para desvincular. De este enlace dependen el logo de las actas **y** el alcance del rol de organización de docs/101 — era un hueco real, no solo cosmético.

### Pantalla `/admin/branding` ("Marca" en el menú)

Protegida por `organizations.branding.manage` o `organizations.manage`. Tres secciones: selector de organización con vista previa y subida del logo; colores y eslogan (el formulario **reenvía el `logo_url` vigente** al guardar, porque `PUT /branding` pisa todos los campos y omitirlo borraría el logo recién subido); y la tabla de proyectos con vincular/desvincular a la organización seleccionada.

## Bug real encontrado por la verificación en vivo (y su fix)

La primera subida real guardó `logo_url` como `http://localhost/api/...` — **sin el puerto `:8000`**. Causa raíz: `deploy/nginx.backend-lb.conf` usaba `proxy_set_header Host $host`, y la variable `$host` de nginx **descarta el puerto** del header original. El backend deriva la URL absoluta del logo del header Host que recibe (`request.base_url`), así que cualquier despliegue en puerto no estándar generaba URLs rotas. Fix: `$http_host`, que preserva el header tal cual lo mandó el cliente. Esto no lo habría encontrado ningún test unitario — el TestClient de Starlette no pasa por nginx.

## Pruebas

`backend/tests/test_branding_logo.py` (8 pruebas nuevas): subida guarda el archivo y el endpoint público lo sirve byte a byte con el content-type correcto; la subida preserva colores/eslogan ya configurados; tipo no soportado y tamaño excedido → 422; sin permiso → 403 y organización inexistente → 404; re-subida en otro formato elimina el archivo anterior; público → 404 sin logo cargado; `PATCH /projects` vincula, desvincula, 403 sin permiso y 404 con proyecto u organización inexistentes; `logo_file_for_url` resuelve solo URLs propias (una URL de CDN externa devuelve `None`).

Nota de entorno: el fixture usa `tempfile.mkdtemp()` en vez del `tmp_path` de pytest — en esta máquina Windows el directorio base `pytest-of-Pedro` está bloqueado (el mismo problema conocido que afecta a `test_file_upload`/`test_health`), y `tmp_path` fallaba con `PermissionError` antes de ejecutar nada.

Suite completa: backend **431 passed** (423 previos + 8 nuevos, mismos 5 errores conocidos no relacionados), frontend 101/101 con el caso nuevo de ruta en `routeConfig.test.ts`, `tsc --noEmit` y `npm run build` limpios.

## Verificación en vivo (stack Podman completo, imágenes reconstruidas)

- Subida real de un PNG de 200×80 vía `POST /branding/logo` → archivo en el volumen compartido, `GET /public/branding-logo/{id}` devolvió los **bytes idénticos** con `image/png`.
- Encontrado y corregido el bug del puerto (sección anterior); tras el fix, la URL guardada quedó `http://localhost:8000/...` correcta.
- `PATCH /identity/projects/demo-project-infomatt360` vinculó el proyecto demo a la "Organizacion por defecto".
- **La prueba culminante:** se creó una plantilla de acta con bloque logo y se generó el PDF de un registro demo real — `pypdf` confirmó **una imagen incrustada de exactamente 200×80** (las dimensiones del logo subido) dentro del PDF, además del encabezado resuelto y la línea de firma. El pipeline completo funciona: subida → volumen compartido → resolución local en el render → PDF con logo.
- En el navegador real: la barra lateral pasó a mostrar el logo (antes solo texto), el menú tiene "Marca", y `/admin/branding` renderiza las tres secciones con la vista previa del logo y el proyecto demo listado como vinculado, sin errores de consola.
- Limpieza: se eliminó la plantilla de acta de prueba directo en la base demo (no existe endpoint DELETE, mismo precedente que docs/109/110). El logo de prueba (rectángulo azul) y el vínculo del proyecto demo **se dejaron a propósito**: son estado real utilizable creado por los flujos reales, y el usuario los va a reemplazar/ajustar desde la misma pantalla.

## Lo que queda fuera (de la misma devolución del usuario)

Los otros tres puntos de la devolución que originó esto siguen pendientes como trabajos separados: densidad visual (letra/espacios más compactos en todo el sistema), tabla de registros estilo KoboToolbox (ocultar columnas, buscador por columna, selector de filas por página, columnas fijas), y firma como imagen en las actas (hoy es línea para firma física, por decisión de alcance de docs/109).
