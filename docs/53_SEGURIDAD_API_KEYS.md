# Seguridad - API Key Authentication

## Objetivo

Permitir integraciones externas sin usar usuario/contrasena ni tokens JWT personales.

## Estado

Implementado para claves por proyecto.

## Formato de clave

```text
im360_<key_id>_<secret>
```

El sistema guarda:

- `key_id` para buscar la clave;
- hash del secreto;
- permisos;
- perfil de volumen;
- estado;
- ultimo uso.

El secreto completo solo se muestra una vez al crear la clave.

## Header requerido

```http
X-API-Key: im360_xxxxx_secret
```

## Endpoints administrativos

```text
POST /api/v1/api-keys/
GET /api/v1/api-keys/{project_id}
DELETE /api/v1/api-keys/{project_id}/{key_id}
```

Crear y revocar claves requiere:

```text
integrations.api_keys.manage
```

## Endpoint de verificacion

```text
GET /api/v1/api-keys/auth/check
```

Permite probar que una clave esta activa y conocer su proyecto/permisos.

## Interfaz web

Pantalla disponible:

```text
/admin/api-keys
```

Permite:

- listar claves del proyecto;
- crear una nueva clave;
- copiar el secreto completo solo al momento de creacion;
- revocar claves activas;
- consultar permisos, estado y ultimo uso.
- seleccionar perfil de volumen: `standard`, `high_volume` o `trusted_sync`.

## Perfiles de volumen

```text
standard      -> uso normal de integraciones.
high_volume   -> sincronizaciones de alto volumen.
trusted_sync  -> integraciones confiables con volumen masivo sin limite estricto global.
```

Para integraciones que sincronizan millones de registros, usar `high_volume` o `trusted_sync` y preferir endpoints bulk/lotes.

Ver:

```text
docs/54_API_BULK_SINCRONIZACION.md
```

## Seguridad aplicada

- No se almacena la clave completa.
- El secreto se compara con `hmac.compare_digest`.
- Las claves pueden revocarse.
- Se registra `last_used_at`.
- Las claves funcionan junto al rate limiting global.

## Pendientes recomendados

- auditoria detallada por uso de API key;
- expiracion programada;
- scopes predefinidos por tipo de integracion;
- rate limiting especifico por API key.
