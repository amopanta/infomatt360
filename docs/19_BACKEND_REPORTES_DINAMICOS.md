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
GET /api/v1/reports/project/{project_id}/summary
GET /api/v1/reports/project/{project_id}/summary.xlsx
POST /api/v1/reports/links
```

## Resumen operativo MVP

El endpoint `/summary` entrega un reporte ejecutivo por proyecto sin crear
tablas nuevas:

```text
records_total
records_by_status
templates[]
  - template_id
  - template_name
  - records_total
  - records_by_status
  - percent_of_total
  - last_record_at
```

La pantalla web `/reports` consume este resumen y permite abrir rápidamente los
registros de cada formulario. Todas las consultas validan que el usuario tenga
asignacion activa al proyecto.

La descarga `/summary.xlsx` genera un libro Excel real sin dependencias externas,
con hojas `Resumen`, `Estados` y `Formularios`. Las celdas de texto que pueden
activar formulas en Excel se neutralizan con prefijo seguro.

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
