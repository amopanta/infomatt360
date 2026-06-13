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
localStorage.infomatt360_token
localStorage.infomatt360_project_id
```

## Componentes MVP

- TEXT;
- NUMBER;
- DATE;
- BOOLEAN basico pendiente de refinar;
- TEXTAREA.

## Pendientes

- mejorar SELECT;
- usar ancho responsive de columnas;
- integrar login real;
- manejar errores visuales;
- pruebas de renderizado;
- conectar con dashboard administrativo.
