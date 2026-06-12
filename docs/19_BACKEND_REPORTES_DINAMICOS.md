# Backend - Reportes Dinamicos

## Objetivo
Crear la base para reportes dinamicos, filtros, visualizaciones y enlaces publicados.

## Archivos agregados

```text
backend/app/models/reports.py
backend/app/schemas/reports.py
backend/app/services/report_service.py
backend/app/api/v1/reports.py
backend/alembic/versions/0016_reports.py
```

## Capacidades iniciales

- crear reporte por proyecto;
- listar reportes por proyecto;
- guardar consulta en JSON;
- guardar layout visual en JSON;
- crear enlace publicado;
- definir modo de acceso;
- permitir o bloquear descarga.

## Endpoints

```text
POST /api/v1/reports/
GET /api/v1/reports/project/{project_id}
POST /api/v1/reports/links
```

## Tipos previstos

- table;
- chart;
- map;
- kpi;
- pivot;
- executive.

## Pendientes

- ejecutar consulta real;
- motor de agregaciones;
- exportar Excel, CSV, PDF y JSON;
- imprimir reporte;
- proteger enlaces con vencimiento;
- IA para analisis ejecutivo.
