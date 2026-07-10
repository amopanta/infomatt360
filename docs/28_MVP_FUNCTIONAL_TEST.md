# Prueba Funcional MVP - Builder a Runtime

## Objetivo
Validar el flujo minimo funcional de InfoMatt360:

```text
Builder
  -> Crear plantilla
  -> Runtime
  -> Capturar
  -> Guardar
  -> Consultar
```

## Precondiciones

- Backend ejecutandose.
- Frontend ejecutandose.
- Base de datos migrada hasta la cabeza Alembic vigente.
- Usuario autenticado con access token en memoria y refresh token en cookie httpOnly.
- Proyecto activo seleccionado en `localStorage.infomatt360_project_id`.

## Flujo de prueba

### 1. Abrir Builder

```text
/builder
```

### 2. Crear plantilla de caracterizacion

Presionar:

```text
Crear plantilla de caracterizacion
```

Resultado esperado:

```text
Plantilla creada: {template_id}
Abrir Runtime
```

### 3. Abrir Runtime

Presionar:

```text
Abrir Runtime
```

Resultado esperado:

```text
/runtime/{template_id}
```

con campos:

```text
Nombre completo
Documento
Municipio
Celular
```

### 4. Guardar respuesta

Diligenciar los campos y presionar:

```text
Guardar respuesta
```

Resultado esperado:

```text
Respuesta guardada correctamente.
```

### 5. Consultar registro por API

```text
GET /api/v1/runtime/template/{template_id}/records
```

Resultado esperado:

```text
Lista de registros guardados con sus valores.
```

## Criterio de aceptacion
El MVP queda funcional si el registro creado desde Runtime aparece en la consulta de registros de la plantilla.

## Automatizacion backend

El flujo completo Builder -> Layout -> Runtime -> Guardar -> Consultar se
ejecuta en la suite automatizada sobre una base aislada. La misma prueba valida
que un usuario sin asignacion al proyecto reciba `403` al intentar consultar la
plantilla, modificar su jerarquia Builder o consultar sus registros. Tambien se
impide asociar una columna de una plantilla con componentes de otra.

## Validacion adicional actual

- `scripts/check-full-stack.cmd` valida backend, frontend, login demo, sesion y modulos principales.
- `scripts/check-browser-cors.cmd` valida CORS real de navegador para `localhost` y `127.0.0.1`.
- Frontend cuenta con contrato de rutas y permisos administrativos testeado con Vitest.

## Pendientes detectados

- Automatizar interaccion visual profunda con Playwright o Cypress si se incorpora una dependencia e2e.
