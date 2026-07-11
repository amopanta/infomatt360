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

## Inventario validado

El catalogo canonico fue contrastado con `LISTA DE CAMPOS.xlsx`. Incluye tambien
INTEGER, DECIMAL, DROPDOWN, DATETIME, AUDIO, VIDEO, GEOTRACE, GEOSHAPE, REPEAT,
MATRIX, CALCULATE, REFERENCE, NPS, RATING y RANKING. `NUMBER`, `FILE` y `OCR` se
conservan como capacidades adicionales de InfoMatt360.

La matriz comparativa enriquecida amplio el inventario con EMAIL, PHONE, URL,
DOCUMENT_ID, YEAR, MONTH, WEEK, PERCENTAGE, CURRENCY, LIKERT_5, LIKERT_7, PDF, MULTIFILE,
PARENT_CHILD, LOOKUP, HIDDEN y metadatos de sistema/auditoria. Regex e IF son
configuraciones de validacion y relevancia; API, seguridad, casos, dashboards,
offline e IA son modulos de plataforma y no tipos de campo.

`DOCUMENT_ID` representa numeros de documento como texto controlado, no como
numero matematico. Permite apariencias como solo numeros, alfanumerico, pasaporte,
NIT/RUT o patron personalizado. Esto conserva letras, guiones y ceros iniciales.

## Pendientes H-01

- paginas;
- secciones;
- filas;
- columnas;
- reglas avanzadas;
- publicacion;
- vista previa;
- runtime web.
