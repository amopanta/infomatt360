# Runtime Engine MVP

## Decision tecnica
El Runtime MVP se construye despues del Builder Core y Layout Engine para validar el flujo completo antes de agregar mas complejidad.

## Problema corregido
El Builder ya tenia componentes y layout, pero faltaba una relacion explicita entre componente y columna. Se agrego `column_id` a `builder_components` para que el Runtime pueda renderizar cada campo en la posicion correcta.

## Archivos agregados

```text
backend/app/schemas/runtime.py
backend/app/services/runtime_service.py
backend/app/api/v1/runtime.py
backend/alembic/versions/0021_builder_component_column.py
```

## Endpoint inicial

```text
GET /api/v1/runtime/template/{template_id}
```

## Flujo

```text
BuilderTemplate
  -> BuilderPage
  -> BuilderSection
  -> BuilderRow
  -> BuilderColumn
  -> BuilderComponent
  -> Runtime JSON
```

## Salida Runtime

```json
{
  "template_id": "...",
  "name": "Caracterizacion de Hogares",
  "status": "draft",
  "pages": []
}
```

## Pendientes inmediatos

- agregar endpoint para version publicada;
- guardar respuestas desde Runtime;
- consultar respuestas;
- frontend RuntimeRenderer;
- pruebas de integracion del flujo Builder -> Runtime.
