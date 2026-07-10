# Readiness de despliegue

## Objetivo

Separar el chequeo basico de vida (`/health`) de la validacion operativa minima
del backend.

## Endpoint

```text
GET /api/v1/health/ready
```

## Valida

- conexion a base de datos con `SELECT 1`;
- version y ambiente;
- directorio de cargas configurado, existente y escribible;
- URL de frontend configurada;
- origenes CORS permitidos;
- estado de `AUTO_CREATE_TABLES`;
- politica de rate limiting respecto a proxies confiables;
- logging de requests y cabecera de correlacion;
- advertencias de configuracion sensible.

## Advertencias esperadas en desarrollo

- `SECRET_KEY` de desarrollo;
- SMTP no configurado;
- `AUTO_CREATE_TABLES` activo en produccion;
- CORS productivo sin origenes explicitos o con comodin;
- `X-Forwarded-For` solo debe aceptarse si el proxy de entrada esta en `API_RATE_LIMIT_TRUSTED_PROXY_IPS`;
- `node_modules` frontend pendiente si npm no ha podido instalar.

El endpoint devuelve `status: ready` cuando la API puede operar en modo local,
pero sus `warnings` indican ajustes necesarios antes de produccion.

En produccion devuelve `503 not_ready` si una dependencia critica no esta lista,
por ejemplo Redis requerido sin configurar o `UPLOAD_DIRECTORY` inexistente/no
escribible.
