# Backend - Formularios Dinamicos

## Objetivo
Crear la base del motor de formularios dinamicos de InfoMatt360.

## Archivos agregados

```text
backend/app/models/forms.py
backend/app/schemas/forms.py
backend/app/services/form_service.py
backend/app/api/v1/forms.py
backend/alembic/versions/0004_forms_base.py
```

## Capacidades iniciales

- crear formulario por proyecto;
- agregar campos iniciales;
- manejar tipo de campo;
- manejar requerido;
- manejar layout por fila y columna;
- listar formularios por proyecto;
- validar acceso al proyecto antes de operar.

## Endpoints

```text
POST /api/v1/forms/
GET /api/v1/forms/project/{project_id}
```

## Tipos de campo previstos

- text;
- number;
- date;
- select;
- multiselect;
- grid;
- file;
- photo;
- video;
- signature;
- gps;
- qr;
- ocr;
- calculated.

## Pendientes

- versiones de formulario;
- reglas condicionales avanzadas;
- publicacion;
- importacion XLSForm;
- constructor visual web;
- validacion de estructura;
- plantillas reutilizables.
