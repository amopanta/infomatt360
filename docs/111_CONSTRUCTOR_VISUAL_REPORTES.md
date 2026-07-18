# 111. Constructor visual de reportes/tableros

## Qué cierra esto

El ítem #6 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md`: "Constructor visual de reportes/tableros simples" — `report_service.py` solo exponía un resumen fijo (`project_summary`), y `ReportsApp.tsx` renderizaba 3 tarjetas y una tabla fijas, sin ninguna forma de configurar qué se muestra.

**Alcance acordado con el usuario:** el usuario pidió inicialmente algo abierto ("constructor visual de reportes/tablero"); al preguntarle por el tipo de widgets, eligió las **tres** opciones ofrecidas (no solo la mínima recomendada): KPI + tabla por formulario (reusando las métricas ya existentes), gráficos simples (barra/torta), y métricas personalizadas (elegir campo + agregación). Para el almacenamiento, eligió **una sola configuración por proyecto** — la pantalla de Reportes existente se volvió editable in-situ, no un sistema de tableros múltiples con nombre (a diferencia de las plantillas de acta, docs/109/110).

## Diseño

### Modelo nuevo, no reusar `Report`/`ReportLink`

`Report`/`ReportLink` (`backend/app/models/reports.py`) ya existían pero completamente sin usar por ninguna UI — están pensados para una **lista** de reportes nombrados con una consulta obligatoria (`query_json` NOT NULL). Forzar "una sola configuración por proyecto" a través de esa tabla habría significado mantener siempre una sola fila con un `name`/`query_json` sin sentido real. Se agregó un modelo nuevo y dedicado, `ReportBoard` (tabla `report_boards`), con `UNIQUE(project_id)` — la restricción "uno por proyecto" queda codificada en el esquema mismo. Se evitó deliberadamente la palabra "Dashboard" en todo el feature (modelos, rutas, módulo de frontend) porque ese término ya lo tiene tomado la pantalla de aterrizaje tras el login (`app/api/v1/dashboard.py`/`dashboard_service.py`, una funcionalidad completamente distinta).

### Union discriminada de widgets, resuelta 100% del lado del servidor

Igual que el constructor visual de actas (docs/109): `ReportBoard.widgets_json` persiste una lista de widgets (`backend/app/schemas/report_board.py`) — `kpi` (una cifra), `table` (el mismo resumen por formulario de siempre, solo con título configurable), `chart` (barra o torta). La "métrica personalizada" **no es un cuarto tipo de widget** sino una *fuente* de datos que `kpi`/`chart` pueden usar (`custom_metric`/`custom_metric_by_status`, campo + agregación), junto a las fuentes ya existentes (total de registros, conteo por estado, conteo por formulario, desglose por estado, totales por formulario) — esto evita una explosión combinatoria de tipos de widget.

`GET /reports/project/{id}/board` calcula `project_summary` una sola vez y devuelve, en el mismo response, `widgets` + un arreglo `resolved` alineado por posición con el valor ya calculado de cada uno — el frontend nunca agrega datos, solo pinta lo que ya viene resuelto. Un widget mal configurado (campo inexistente, formulario incorrecto) nunca lanza excepción al resolver: su bucket vacío resuelve a `0`, para que un tablero completo no se rompa por un widget puntual mal armado (la validación real ocurre al **guardar**, no al ver).

### Métricas personalizadas: agregación real sobre `RuntimeRecordValue`

Es la parte genuinamente nueva: no existía ningún código que agregara (suma/promedio/min/max) valores de campo across registros. `_aggregate_custom_metric`/`_aggregate_custom_metric_by_status` (`report_service.py`) decodifican `field_value_json` con el mismo idioma ya usado en `runtime_record_service._next_serial_number`/`acta_service._decode_value_for_display` (`json.loads` + `isinstance(parsed, (int, float)) and not isinstance(parsed, bool)`). Al **guardar** un widget con fuente personalizada, se valida: el formulario pertenece al proyecto, el campo existe en ese formulario, y — si la agregación no es "conteo" — el tipo de campo (`component_type`) es de un catálogo numérico (`NUMBER`, `INTEGER`, `DECIMAL`, `PERCENTAGE`, `CURRENCY`, `RANGE`, `NPS`, `RATING`, `LIKERT_5`, `LIKERT_7`, duplicado en el frontend igual que ya se duplica el catálogo de tipos de campo).

### Permiso: reusar `builder.write`

Editar la estructura de un tablero es la misma clase de acción que ya protege `builder.write` en el resto del repo (constructor de formularios, constructor de actas) — no se creó un permiso nuevo. Ver el tablero solo exige acceso al proyecto, igual que el resumen fijo anterior.

### Gráficos: SVG a mano, sin dependencia nueva

`frontend/package.json` no tenía ninguna librería de gráficos, y este repo ya había evitado dependencias nuevas dos veces para necesidades equivalentes (xhtml2pdf en vez de WeasyPrint; drag HTML5 nativo en vez de una librería de DnD). `frontend/src/modules/reports/chartGeometry.ts` calcula la geometría de barra y torta como funciones puras (coordenadas SVG `<rect>`/`<path>`), sin dependencia nueva. El constructor (`ReportBoardEditor.tsx`) reordena por arrastre con el mismo patrón HTML5 nativo ya probado en `ActaCanvas.tsx` (docs/109).

## Pruebas

`backend/tests/test_report_board.py` (7 pruebas nuevas): sin configuración guardada, el tablero por defecto resuelve correctamente contra registros reales; `PUT` sin `builder.write` → 403; `custom_metric` sobre un campo no numérico con `aggregation=sum` → 422; `custom_metric` apuntando a un formulario de otro proyecto → 422; guardar y luego consultar un KPI de promedio (valores 4/3/5) resuelve exactamente `4.0`; un gráfico `custom_metric_by_status` agrupa correctamente por estado; `status_breakdown`/`template_totals` coinciden exactamente con lo que ya calcula `project_summary` (guarda contra desviación entre ambos).

`frontend/src/modules/reports/widgetOrder.test.ts` (5 pruebas) y `chartGeometry.test.ts` (7 pruebas): lógica pura de reordenamiento y geometría de gráficos — alturas de barra proporcionales, gráfico en 0 cuando el máximo es 0, porcentajes de torta suman ~100, el caso de un solo punto (100%, donde el arco SVG estándar no funciona para un círculo completo) genera un path válido usando dos semicírculos en vez de romper. Sin tests de render de componentes React, consistente con el resto del repo.

Suite completa tras el cambio: backend 387/387 (380 previos + 7 nuevos, mismos 5 errores preexistentes ya documentados), frontend 81/81 (69 previos + 12 nuevas), `tsc --noEmit` y `npm run build` limpios.

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`), tras aplicar `alembic upgrade head`:

- El tablero por defecto renderizó correctamente con datos reales del proyecto (KPI "Registros totales" = 6, tabla por formulario, torta de estados con leyenda y porcentajes).
- Se hizo clic en "Personalizar tablero", se agregó un KPI con fuente "Métrica personalizada" (formulario Caracterizacion demo, campo `integrantes`, agregación promedio) y un gráfico de barras con "Métrica personalizada por estado" (mismo campo, suma) — se guardó (`PUT .../board` real, 200 OK).
- Los valores resueltos fueron correctos contra los datos reales: KPI = `4` (promedio de 4/3/5), gráfico = `approved: 3` / `submitted: 9` (suma agrupada por estado de los 3 registros demo).
- Se recargó `/reports` en una navegación nueva y se confirmó que persiste el tablero guardado, no el default.
- Se confirmó que "Exportar XLSX" sigue funcionando sin cambios (`/summary.xlsx` no se tocó).
- El chequeo de permiso (`PUT` sin `builder.write` → 403) no se repitió en vivo por no haber una cuenta demo sin ese permiso a mano — queda cubierto de forma concluyente por la prueba de pytest dedicada, que sí lo verifica de forma aislada.
- Se eliminó la fila de `report_boards` de prueba directo en la base de datos demo (no existe endpoint DELETE); `backend/.env` y `frontend/.env.local` se revirtieron.

## Lo que queda fuera de esta sesión

Con esto se cierran los 6 primeros ítems de docs/96 (#1-#6). Quedan #7 (descarga masiva de evidencias en ZIP), #8 (GIS real con PostGIS), #9 (conectores BI nombrados), #10 (impresión nativa masiva de escritorio) y #11 (bandeja de correo externa vía IMAP).
