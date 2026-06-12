# Backend - Programador de Tareas

## Objetivo
Crear la base para programar procesos internos y sincronizaciones.

## Archivos agregados

```text
backend/app/models/scheduler.py
backend/app/schemas/scheduler.py
backend/app/services/scheduler_service.py
backend/app/api/v1/scheduler.py
backend/alembic/versions/0015_scheduler.py
```

## Capacidades iniciales

- crear tarea programada por proyecto;
- listar tareas por proyecto;
- registrar ejecuciones;
- listar ejecuciones por tarea;
- preparar frecuencia manual, horaria, diaria o semanal.

## Endpoints

```text
POST /api/v1/scheduler/tasks
GET /api/v1/scheduler/tasks/{project_id}
POST /api/v1/scheduler/runs
GET /api/v1/scheduler/runs/{task_id}
```

## Tipos previstos

- integration_sync;
- etl_pipeline;
- mirror_sync;
- report_export;
- ai_review;
- cleanup.

## Pendientes

- worker real;
- cola Redis;
- APScheduler o Celery;
- reintentos;
- bloqueo de ejecuciones duplicadas;
- logs detallados;
- alertas por error.
