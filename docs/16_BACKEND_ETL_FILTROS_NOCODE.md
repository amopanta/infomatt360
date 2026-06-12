# Backend - Motor ETL y Filtros No-Code

## Objetivo
Crear la base para seleccionar campos, aplicar filtros y definir transformaciones sin programar.

## Archivos agregados

```text
backend/app/models/etl.py
backend/app/schemas/etl.py
backend/app/services/etl_service.py
backend/app/api/v1/etl.py
backend/alembic/versions/0013_etl.py
```

## Capacidades iniciales

- crear reglas ETL;
- listar reglas por proyecto;
- crear pipelines ETL;
- listar pipelines por proyecto;
- guardar operador, valor y configuracion JSON;
- guardar pasos de pipeline en JSON.

## Endpoints

```text
POST /api/v1/etl/rules
GET /api/v1/etl/rules/{project_id}
POST /api/v1/etl/pipelines
GET /api/v1/etl/pipelines/{project_id}
```

## Tipos de regla previstos

- select_field;
- rename_field;
- filter_record;
- transform_value;
- convert_type;
- default_value;
- split_field;
- merge_fields.

## Pendientes

- motor de ejecucion real;
- vista previa de resultados;
- conteo de registros antes de importar;
- validacion de reglas;
- transformaciones avanzadas;
- logs por ejecucion;
- integracion con jobs programados.
