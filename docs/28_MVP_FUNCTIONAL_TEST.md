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
- Base de datos migrada hasta `0022_runtime_records`.
- Usuario autenticado con token en `localStorage.infomatt360_token`.
- Proyecto activo en `localStorage.infomatt360_project_id`.

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

## Pendientes detectados

- Integrar login real en frontend.
- Remplazar localStorage manual por contexto de sesion.
- Crear vista web de consulta de registros.
- Automatizar esta prueba con Playwright o Cypress.
