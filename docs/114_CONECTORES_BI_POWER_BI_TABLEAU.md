# 114. Conectores REST para Power BI y Tableau

## Qué cierra esto

El ítem #9 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md` (verdict **FALTA**): "Conectores formales para Power BI / Looker / Tableau / Metabase / Superset (§19) — Solo existe una API de lectura genérica (`external_api.py`), sin conectores nombrados a esas herramientas."

**Decisión de alcance acordada con el usuario:** REST. De las 5 herramientas, Power BI y Tableau se conectan por REST — se extendió `external_api.py` (que ya existía con autenticación por API key) y se construyó un conector real para cada una. Looker/Metabase/Superset necesitan en la práctica una conexión SQL real (JDBC/ODBC-class), que ya es el terreno de la función Mirror/Base Espejo (`docs/102`, ítem #1 de la misma auditoría) — madurar Mirror quedó explícitamente fuera de alcance de este ítem.

## Diseño

### Las dos brechas reales que tenía `external_api.py`

`GET /external-api/records` ya resolvía auth (API key) y filtrado por proyecto, pero devolvía los registros en forma anidada tipo EAV (`values: [{field_name, field_value_json}]`) — inutilizable directamente por una herramienta BI que espera columnas — y no tenía ningún cursor incremental, obligando a cualquier refresco programado a re-descargar todo el dataset cada vez.

Se agregaron 3 rutas nuevas, con el mismo criterio de permiso (`records.read`) y las mismas verificaciones de proyecto que las rutas existentes:
- `GET /external-api/records/tabular?template_id=&status=&updated_since=&limit=&offset=` — filas planas con columnas estables, derivadas del esquema del formulario (`BuilderComponent`, ordenado por `sort_order`), no de qué campos aparecieron en el lote actual (a diferencia de `export_template_csv`, cuyo conjunto de columnas varía según el resultado). `updated_since` filtra por `RuntimeRecord.updated_at`, normalizado a UTC naive con la nueva función pública `app.core.time.to_naive_utc` (promovida desde una copia privada que ya existía en `api_key_service.py`, mismo gotcha de datetime naive/aware ya documentado en docs/105).
- `GET /external-api/templates` — lista los formularios del proyecto de la API key.
- `GET /external-api/templates/{id}/schema` — el esquema de campos de un formulario (nombre, etiqueta, tipo), necesario para que un conector BI sepa qué columnas existen antes de pedir datos.

Los valores de campo que lleguen a `/records/tabular` pasan por el mismo blindaje anti-inyección de fórmulas que ya protege la exportación CSV interna (`_safe_csv_cell`) — un valor pulido desde Power BI/Tableau puede terminar pegado en Excel/Sheets por el analista, mismo riesgo. Se extrajo el chequeo compartido (`_is_formula_like`) y se aplicó una versión que preserva tipos JSON (`_safe_bi_scalar`) en vez de convertir todo a texto.

### Power BI: documentación, no código construido

Un conector certificado de Power BI (`.mez`/`.pqx`) requiere el Power Query SDK de Microsoft — una herramienta separada, no algo que este repo pueda construir o probar. El entregable honesto es un snippet de Power Query M documentado más abajo (patrón "Blank Query"), no código "construido y probado" como el resto de este cambio.

### Tableau: un Web Data Connector real

A diferencia de Power BI, Tableau sí tiene un entregable genuinamente construible: un Web Data Connector es una página HTML+JS estática que implementa la API JS de Tableau. Se agregó `frontend/tableau-wdc/index.html` como una segunda entrada de build en Vite (`rollupOptions.input` pasó de un string único a un mapa `{main, 'tableau-wdc'}`, patrón documentado de Vite para apps multi-página), excluida del precache de la PWA (`workbox.globIgnores`) porque no es parte de la app instalable.

Toda la lógica real vive en `frontend/src/integrations/tableauWdc/` como módulos TypeScript normales (type-checados por `tsc -b`, testeables con vitest): `schemaMapping.ts` traduce el esquema de campos de InfoMatt360 al formato de columnas de Tableau (mapeo de tipos, deduplicación por nombre de campo), `rowMapping.ts` aplana el sobre fijo + campos del formulario en filas planas (sin sobrescribir columnas de metadata si un campo de formulario colisiona de nombre, serializando a JSON los valores no escalares como GPS/REPEAT/MATRIX que caigan en una columna de tipo texto). `main.ts` es un wrapper delgado sobre `tableau.registerConnector(...)` que llama a las 3 rutas nuevas.

### Looker / Metabase / Superset: no se construyen conectores REST simulados

Estas tres herramientas quieren una conexión SQL real, no REST. `docs/102_BASE_ESPEJO_REAL.md` ya hace esta conexión explícita (línea 11: *"Postgres... es el destino típico para BI/analítica (Power BI/Metabase/Superset, hallazgo #9)"*). El camino recomendado hasta que Mirror madure: correr un `MirrorPlan` hacia un destino Postgres, y conectar el driver nativo de Postgres de Looker/Metabase/Superset a esa base — con las limitaciones ya documentadas en `docs/102` sin sobrevender: sync solo manual (sin integración con `ScheduledTask`), solo Postgres/SQLite (sin MySQL/SQL Server), misma estructura EAV que el motor interno (sin tabla ancha pivotada por formulario), sin UI de administración.

## Snippet de Power Query M (Power BI)

Pegar en Power BI Desktop → Obtener datos → Consulta en blanco → Editor avanzado. Se recomienda convertir `ApiBaseUrl`/`ApiKey`/`TemplateId` en Parámetros de Power Query en vez de dejarlos hardcodeados en la consulta.

```m
let
    ApiBaseUrl = "https://TU-DOMINIO/api/v1",
    ApiKey = "REEMPLAZAR_CON_TU_API_KEY",
    TemplateId = "REEMPLAZAR_CON_EL_ID_DEL_FORMULARIO",

    GetPage = (offset as number) =>
        let
            Response = Web.Contents(
                ApiBaseUrl & "/external-api/records/tabular",
                [
                    Headers = [#"X-API-Key" = ApiKey],
                    Query = [ template_id = TemplateId, status = "approved", limit = "100", offset = Text.From(offset) ]
                ]
            ),
            Json = Json.Document(Response)
        in
            Json,

    FirstPage = GetPage(0),
    Total = FirstPage[total],
    PageSize = FirstPage[limit],
    Offsets = List.Generate(() => 0, each _ < Total, each _ + PageSize),
    AllItems = List.Combine(List.Transform(Offsets, each GetPage(_)[items])),
    ItemsTable = Table.FromList(AllItems, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    Expanded = Table.ExpandRecordColumn(ItemsTable, "Column1", {"record_id", "status", "submitted_by", "participant_id", "created_at", "updated_at", "fields"}),
    ExpandedFields = Table.ExpandRecordColumn(Expanded, "fields", FirstPage[columns])
in
    ExpandedFields
```

Para refrescos programados en Power BI Service, se recomienda crear una `ProjectApiKey` dedicada con `rate_limit_profile="high_volume"` o `"trusted_sync"` (UI ya existente en `/admin/api-keys`, sin cambio de backend) — el API key nunca va en la query string, siempre en `Headers`.

## Instrucciones para Tableau

Tras `npm run build`, servir `dist/tableau-wdc/index.html` (puede ser el mismo dominio que sirve la SPA, en la ruta `/tableau-wdc/`). En Tableau Desktop: Conectar → Más → Conector de datos web → pegar la URL de esa página. Completar URL base de la API, API key, ID de formulario y filtro de estado en el formulario, presionar "Obtener datos".

## Pruebas

`backend/tests/test_external_api.py` (9 pruebas nuevas sobre el fixture existente, extendido con `BuilderComponent`s, `updated_at` explícitos y distintos en los registros sembrados, y un valor con forma de fórmula): columnas estables entre llamadas con distinto filtro de estado; `updated_since` filtra incremental e inclusivamente en el límite; `updated_since` con sufijo `Z` (aware) no rompe — regresión directa del gotcha naive/aware de docs/105; un valor tipo fórmula vuelve con el prefijo `'`; `/records/tabular` y `/templates/{id}/schema` rechazan plantilla de otro proyecto; `/templates` solo devuelve las del proyecto de la API key y exige `records.read`; `/templates/{id}/schema` respeta el orden de `sort_order`; los 3 endpoints nuevos exigen `X-API-Key`.

`frontend/src/integrations/tableauWdc/{schemaMapping,rowMapping}.test.ts` (13 pruebas nuevas): cada bucket de mapeo de tipo de columna + fallback a texto; las 6 columnas fijas de metadata siempre presentes y primero; deduplicación de nombre de campo repetido (gana el último); forma de fila plana correcta; valor ausente/null preservado como `null`; colisión de nombre con columna de metadata (gana la metadata); valor no escalar en columna de texto se serializa a JSON.

Suite completa tras el cambio: backend 413/413 (405 previos + 8 nuevos, mismos 5 errores preexistentes ya documentados), frontend 98/98 (85 previos + 13 nuevos), `tsc --noEmit` limpio, `npm run build` genera correctamente `dist/tableau-wdc/index.html` como entrada separada sin romper el build de la SPA principal.

**Límite explícito, no fingido:** la integración real de Tableau (invocación de `getSchema`/`getData` por el software de Tableau) no puede probarse extremo a extremo sin Tableau Desktop/Server real — no disponible en este entorno. Cubierto por revisión de código y por la verificación en vivo descrita abajo (la librería JS real de Tableau, cargada desde su CDN oficial, registra el conector sin error, y la misma función de fetch que usan `getSchema`/`getData` se ejerció en vivo desde la página del conector contra el backend real).

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`):

- Se creó una `ProjectApiKey` real ("BI connector test", permiso `records.read`) desde `/admin/api-keys`.
- `GET /external-api/templates` devolvió los 14 formularios reales del proyecto.
- `GET /external-api/templates/demo-template-characterization/schema` devolvió los 4 campos reales (`nombre`, `integrantes`, `ubicacion`, `observaciones`) en el orden correcto.
- `GET /external-api/records/tabular` con y sin filtro de estado devolvió las mismas 4 columnas estables en ambas respuestas (3 registros sin filtro, 1 con `status=approved`), confirmando en vivo el fix de esquema estable — incluyendo un campo `GPS` (`ubicacion`) que llegó como el objeto GeoJSON real, sin aplanar.
- `updated_since` filtrado incrementalmente contra fechas reales de los registros demo: una fecha de corte reciente excluyó correctamente el registro más viejo; una fecha futura devolvió 0 registros.
- Se abrió `tableau-wdc/index.html` vía el servidor de desarrollo — la librería JS real de Tableau (cargada desde `connectors.tableau.com`) inicializó y registró el conector sin error (confirmado en la consola: "Connector registered", logs propios de la librería de Tableau). El botón "Listar formularios" de la página (que usa la misma función de fetch que `getSchema`/`getData`) trajo los 14 formularios reales del backend.
- Se revocó la `ProjectApiKey` de prueba directamente en la base de datos demo tras la verificación (no se creó ningún otro dato de prueba).
- Se revirtieron `backend/.env` (línea `CORS_ALLOWED_ORIGINS`) y se eliminó `frontend/.env.local`.

## Lo que queda fuera de esta sesión

Con esto se cierran 9 de los 14 hallazgos de docs/96 (#1-#9), con el ítem #9 actualizado de **FALTA** a **PARCIAL** (conectores REST reales para Power BI y Tableau; hand-off documentado y honesto hacia Mirror para Looker/Metabase/Superset). Quedan #10 (impresión nativa masiva de escritorio) y #11 (bandeja de correo externa vía IMAP).
