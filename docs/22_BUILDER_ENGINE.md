# H-01 Builder Engine Core

## Objetivo
Construir el motor visual de formularios de InfoMatt360.

## Archivos agregados

```text
backend/app/models/builder.py
backend/app/schemas/builder.py
backend/app/services/builder_service.py
backend/app/api/v1/builder.py
backend/alembic/versions/0019_builder.py
```

## Capacidades iniciales

- crear plantilla visual por proyecto;
- listar plantillas;
- agregar componentes;
- crear versiones de formulario;
- guardar schema interno en JSON;
- preparar publicacion y runtime.

## Endpoints

```text
POST /api/v1/builder/templates
GET /api/v1/builder/templates/{project_id}
POST /api/v1/builder/components
POST /api/v1/builder/versions
```

## Componentes previstos

- TEXT;
- NUMBER;
- DATE;
- TIME;
- BOOLEAN;
- SELECT;
- MULTISELECT;
- TEXTAREA;
- GPS;
- SIGNATURE;
- IMAGE;
- FILE;
- OCR;
- QR;
- BARCODE.

## Pendientes H-01

- paginas;
- secciones;
- filas;
- columnas;
- reglas avanzadas;
- publicacion;
- vista previa;
- runtime web.
