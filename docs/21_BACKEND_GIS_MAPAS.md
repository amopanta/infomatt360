# Backend - GIS, Mapas y Coordenadas

## Objetivo
Crear la base para manejo geografico, captura GPS, capas, puntos, poligonos y futuras integraciones con QGIS y ArcGIS.

## Archivos agregados

```text
backend/app/models/gis.py
backend/app/schemas/gis.py
backend/app/services/gis_service.py
backend/app/api/v1/gis.py
backend/alembic/versions/0018_geo.py
```

## Capacidades iniciales

- crear capas por proyecto;
- listar capas;
- crear elementos geograficos;
- asociar elementos a capas;
- asociar coordenadas a participantes o registros;
- guardar geometria en JSON;
- guardar propiedades flexibles;
- listar elementos por proyecto o capa.

## Endpoints

```text
POST /api/v1/gis/layers
GET /api/v1/gis/layers/{project_id}
POST /api/v1/gis/features
GET /api/v1/gis/features/{project_id}
```

## Pendientes

- GeoJSON real;
- exportacion para QGIS;
- integracion ArcGIS;
- mapas de calor;
- poligonos;
- rutas;
- validacion de coordenadas;
- visor de mapa en frontend.
