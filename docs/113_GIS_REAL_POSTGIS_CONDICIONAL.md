# 113. GIS real: geometría PostGIS condicional + mapa Leaflet

## Qué cierra esto

El ítem #8 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md` (verdict **PARCIAL**): "GIS real: columnas de geometría PostGIS, GeoJSON, WMS/WFS (§19)". Antes de este cambio, `GisFeature` guardaba lat/lng como `String` y `geometry_json` como texto validado — sin columna de geometría real, sin PostGIS/GeoAlchemy2, sin WMS/WFS. El mapa (`MapsApp.tsx`) era un `<svg>` dibujado a mano que solo plotaba un punto centroide por elemento, sin basemap, zoom/pan real, ni renderizado de líneas/polígonos.

**Decisiones de alcance acordadas con el usuario:**
1. PostGIS/GeoAlchemy2 solo aplica cuando el proyecto corre sobre Postgres+PostGIS (producción). SQLite (dev/demo/tests) conserva el almacenamiento actual con cómputo espacial en Python de respaldo — nadie necesita instalar PostGIS para desarrollar localmente. Opción recomendada, elegida explícitamente sobre forzar PostGIS incluso en desarrollo.
2. Se omite el protocolo OGC WMS/WFS literal. En su lugar: mapa interactivo real con Leaflet + teselas OpenStreetMap, más una API GeoJSON con búsqueda por radio que cumple el mismo propósito práctico. Opción recomendada, elegida explícitamente sobre implementar WFS.

## Diseño

### Columna de geometría dialect-aware

`backend/app/db/geo_types.py` define `Geography(TypeDecorator)`: su `load_dialect_impl` resuelve `Geometry` real de GeoAlchemy2 cuando el dialecto del bind es `postgresql`, y cae a `Text` en cualquier otro motor (SQLite). El `import geoalchemy2` es perezoso (dentro del método), así que el módulo nunca requiere el paquete instalado salvo que efectivamente se toque un bind Postgres. `GisFeature` (`backend/app/models/gis.py`) gana una columna nueva `geom` de este tipo, aditiva — `latitude`/`longitude`/`geometry_json` no se tocan, compatibilidad total con filas existentes y con `GisFeatureRead` (que sigue sin exponer `geom`, es un detalle interno de almacenamiento/consulta).

La migración `0068_gis_geometry_column.py` sigue el mismo patrón idempotente (guard por inspección de columnas) que `0067_report_boards.py`: en Postgres ejecuta `CREATE EXTENSION IF NOT EXISTS postgis`, agrega la columna `Geometry` real y crea un índice GiST; en cualquier otro motor solo agrega una columna `TEXT`. Se aplicó exitosamente contra la base demo SQLite existente.

**Nota operativa:** `docker-compose.production.example.yml` usa la imagen `postgres:16` plana, sin PostGIS preinstalado — se agregó un comentario señalando que producción real necesita `postgis/postgis:16-3.4` (u otra imagen con la extensión) para que la migración tenga éxito ahí.

### Búsqueda espacial real

`GisService.nearby_features` se ramifica por dialecto (mismo espíritu que `engine_options()` en `db/session.py`): en Postgres usaría `ST_DWithin` real sobre el índice GiST de `geom` (`_nearby_postgis`, código no ejercitable en este repo sin infraestructura Postgres+PostGIS); en SQLite calcula distancia Haversine en Python sobre el resultado combinado de `project_map` — donde antes no existía ningún concepto de distancia. Nuevo endpoint `GET /gis/features/{project_id}/nearby?lat=&lng=&radius_km=`, mismo criterio de permiso (`user_has_project_access`) que las otras 4 rutas de `gis.py`.

### Corrección de rendimiento en `_runtime_map_features`

Antes, esta función parseaba como JSON *cada* valor de campo de *cada* registro del proyecto buscando algo con forma de GeoJSON — sin filtro en SQL. Se agregó un join contra `BuilderComponent` (por `field_name`+`template_id`, no por `RuntimeRecordValue.component_id`, que queda `NULL` en valores creados vía `runtime_record_service.correct_field`) filtrado a `component_type IN ('GPS','GEOTRACE','GEOSHAPE')`, aplicado *antes* de intentar decodificar JSON. Esto también corrige un caso adversarial real: un campo de texto libre cuyo valor casualmente tiene forma de GeoJSON ya no aparece en el mapa.

### Mapa real con Leaflet

`MapsApp.tsx` se reescribió con `react-leaflet@5` (versión compatible con React 19, confirmada instalada en el proyecto) — se prefirió sobre Leaflet imperativo a mano porque el ciclo de vida de Leaflet (crear el mapa una vez, mutar capas, destruir en cleanup) choca con el modelo declarativo de React; reimplementar esa sincronización a mano habría sido más código que adoptar la dependencia. `Point` → marcador, `LineString` → polilínea real, `Polygon` → polígono real (antes todo se aplastaba a un punto centroide, perdiendo la forma real que el backend ya calculaba y devolvía en `geometry_json` pero el frontend ignoraba). Panel simple de búsqueda por radio (sin kit de dibujo de polígonos): clic en el mapa fija un centro, input de radio, botón de búsqueda contra el nuevo endpoint `/nearby`, botón "Limpiar filtro" vuelve a la vista completa. `frontend/src/modules/runtime/geoEngine.ts` y `RuntimeGeoField.tsx`/`RuntimeGeoMap.tsx` (captura de coordenadas en formularios) no se tocaron — siguen usando su propia vista previa SVG, verificado que `RuntimeGeoMap.tsx` sigue dependiendo de esas funciones.

## Pruebas

`backend/tests/test_gis_geo_types.py` (3 pruebas nuevas): en SQLite, `geom` se pobla como el mismo string GeoJSON que `geometry_json`; la respuesta de `GisFeatureRead` no expone `geom` (regresión de forma); sin coordenadas, `geom` queda `None`.

`backend/tests/test_gis_nearby.py` (3 pruebas nuevas): con coordenadas reales verificables (Plaza de Bolívar, Bogotá, y un punto a 0.01° de latitud ≈ 1.112 km, calculado a mano), radio de 2km devuelve ambos elementos, radio de 0.5km excluye el más lejano; 403 sin acceso al proyecto.

`backend/tests/test_gis_map.py` (actualizado): fixture ahora incluye `BuilderComponent` para el campo geo (necesario tras el fix de `_runtime_map_features`); nuevo caso adversarial — un campo `TEXT` con un valor que casualmente parece GeoJSON no aparece en el mapa.

Suite completa tras el cambio: backend 405/405 (399 previos + 6 nuevos, mismos 5 errores preexistentes ya documentados), frontend 85/85 (sin tests nuevos — este cambio es puramente de UI/mapa, sin lógica pura nueva que aislar), `tsc --noEmit` y `npm run build` limpios.

**Límite explícito, no fingido:** el camino Postgres/PostGIS real (`ST_DWithin`, índice GiST, `CREATE EXTENSION postgis`) no puede verificarse por pytest en este repo — no hay infraestructura Postgres en CI/dev. Queda cubierto por revisión de código; requiere verificación manual/staging cuando exista un entorno Postgres+PostGIS real.

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`, que corre sobre SQLite — solo se ejerció el camino de respaldo, no el real de PostGIS):

- Se aplicó `alembic upgrade head` (migración `0068`) contra la base demo sin errores.
- `/maps` renderizó un mapa Leaflet real: 9/9 teselas de OpenStreetMap cargadas, 4 marcadores reales (verificado vía inspección del DOM: `.leaflet-tile-loaded`, `.leaflet-marker-icon`), contenedor de 560px, atribución OSM visible — no el SVG anterior.
- El panel de búsqueda por radio funcionó extremo a extremo: con radio 5km desde el centro por defecto, `GET /gis/features/{project}/nearby?lat=...&lng=...&radius_km=5` devolvió `200 OK` y la UI se actualizó correctamente a "2 elemento(s) con coordenadas (filtrado por cercanía)" con el botón "Limpiar filtro" visible.
- "Limpiar filtro" restauró correctamente los 4 elementos originales.
- Sin errores en los logs del servidor backend durante toda la sesión de verificación.
- La creación de un `GisFeature` manual vía la UI no se probó en vivo (no existe una pantalla de administración de capas/features en este proyecto, solo la API) — queda cubierta de forma concluyente por `test_gis_geo_types.py`, que sí la verifica de forma aislada; el mapa en vivo sí mostró correctamente elementos de origen `gis` (badge "Capa GIS"), confirmando que la lectura de features manuales existentes funciona sin cambios.
- Se revirtieron `backend/.env` (línea `CORS_ALLOWED_ORIGINS`) y se eliminó `frontend/.env.local`. No se creó ningún dato de prueba nuevo (la sesión solo hizo lecturas y una búsqueda de radio contra datos ya existentes en la demo).

## Lo que queda fuera de esta sesión

Con esto se cierran los 8 primeros ítems de docs/96 (#1-#8). Quedan #9 (conectores BI nombrados), #10 (impresión nativa masiva de escritorio) y #11 (bandeja de correo externa vía IMAP).
