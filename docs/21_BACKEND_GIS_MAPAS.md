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
GET /api/v1/gis/map/{project_id}
```

## Mapa operativo MVP

El endpoint `/map/{project_id}` consolida en una sola respuesta:

- elementos creados en `gis_features`;
- coordenadas guardadas dentro de respuestas Runtime (`Point`, `LineString`,
  `Polygon` o valores simples `lat/lng`);
- metadatos de formulario, registro y campo cuando el origen es Runtime.

La pantalla web `/maps` consume este endpoint y renderiza un mapa SVG local,
sin depender todavia de proveedores externos de cartografia. Para lineas y
poligonos se calcula un punto representativo visual, conservando la geometria
original en `geometry_json`.

## Pendientes

- capas cartograficas externas opcionales;
- exportacion para QGIS;
- integracion ArcGIS;
- mapas de calor;
- exportacion GeoJSON masiva.
