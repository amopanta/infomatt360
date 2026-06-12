# Backend - Base Espejo

## Objetivo
Crear la base para sincronizar estructuras y datos hacia motores externos.

## Archivos agregados

```text
backend/app/models/mirror.py
backend/app/schemas/mirror.py
backend/app/services/mirror_service.py
backend/app/api/v1/mirror.py
backend/alembic/versions/0014_mirror.py
```

## Capacidades iniciales

- crear destino espejo por proyecto;
- listar destinos espejo;
- crear plan de replica;
- listar planes por destino;
- guardar tablas objetivo en JSON;
- preparar modo manual o programado.

## Endpoints

```text
POST /api/v1/mirror/targets
GET /api/v1/mirror/targets/{project_id}
POST /api/v1/mirror/plans
GET /api/v1/mirror/plans/{target_id}
```

## Motores previstos

- postgresql;
- mysql;
- sqlserver;
- oracle;
- sqlite.

## Pendientes

- probar destino;
- crear estructura remota;
- ejecutar replica;
- programar frecuencia;
- logs por ejecucion;
- control de conflictos;
- seguridad de configuracion.
