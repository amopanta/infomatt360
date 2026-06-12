# Backend - Integraciones No-Code

## Objetivo
Crear la base para conectar fuentes externas configurables sin programar.

## Archivos agregados

```text
backend/app/models/integrations.py
backend/app/schemas/integrations.py
backend/app/services/integration_service.py
backend/app/api/v1/integrations.py
backend/alembic/versions/0012_integrations.py
```

## Capacidades iniciales

- crear fuente externa por proyecto;
- listar fuentes externas;
- crear mapeo de campos;
- guardar filtros en JSON;
- crear trabajo de sincronizacion;
- preparar sincronizacion manual o programada.

## Endpoints

```text
POST /api/v1/integrations/sources
GET /api/v1/integrations/sources/{project_id}
POST /api/v1/integrations/maps
POST /api/v1/integrations/jobs
```

## Tipos previstos

- rest;
- csv;
- excel;
- sql;
- sheets;
- kobo;
- odk;
- arcgis.

## Pendientes

- probar conexion;
- descubrir estructura externa;
- selector visual de campos;
- filtros no-code;
- transformaciones;
- ejecucion real de jobs;
- logs de ejecucion;
- base espejo.
