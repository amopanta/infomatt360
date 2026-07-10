# Runtime Renderer Web

## Objetivo
Permitir que el frontend renderice formularios creados desde Builder usando el JSON entregado por Runtime.

## Decision tecnica
Se inicio un frontend minimo con Vite, React y TypeScript para concentrar el esfuerzo en el MVP Runtime, sin construir aun el dashboard completo.

## Archivos agregados

```text
frontend/package.json
frontend/tsconfig.json
frontend/index.html
frontend/src/main.tsx
frontend/src/styles.css
frontend/src/modules/runtime/types.ts
frontend/src/modules/runtime/api.ts
frontend/src/modules/runtime/RuntimeApp.tsx
frontend/src/modules/runtime/RuntimeRenderer.tsx
frontend/src/modules/runtime/RuntimeField.tsx
```

## Ruta MVP

```text
/runtime/{template_id}
```

## Flujo

```text
RuntimeApp
  -> GET /api/v1/runtime/template/{template_id}
  -> RuntimeRenderer
  -> RuntimeField
  -> POST /api/v1/runtime/save
```

## Configuracion requerida

El frontend lee:

```text
VITE_API_BASE_URL
access token en memoria de sesion
refresh token en cookie httpOnly
localStorage.infomatt360_project_id para proyecto activo
```

## Componentes MVP

- TEXT;
- NUMBER;
- DATE;
- BOOLEAN con valor booleano real;
- SELECT y MULTISELECT configurables mediante `config_json.options` o `config_json.choices`;
- TEXTAREA;
- FILE, PDF, MULTIFILE, IMAGE, AUDIO y VIDEO con carga multipart;
- SIGNATURE con lienzo tactil y exportacion PNG;
- GPS, GEOTRACE y GEOSHAPE con captura GeoJSON;
- visor GIS vectorial offline con captura tactil;
- columnas responsive para escritorio, tableta y movil.
- inicio de sesion, seleccion de proyecto y cambio obligatorio de clave temporal;
- recuperacion por token y administracion de correo/clave por usuario autorizado.
- consulta web de formularios y registros en `/records`, con busqueda y detalle expandible.

## Pendientes

- agregar capas cartograficas externas opcionales;
- configurar las credenciales SMTP del ambiente de despliegue;
- unificar el manejo visual de errores;
- ampliar pruebas visuales de renderizado;
- seguir enriqueciendo dashboard administrativo segun piloto.
