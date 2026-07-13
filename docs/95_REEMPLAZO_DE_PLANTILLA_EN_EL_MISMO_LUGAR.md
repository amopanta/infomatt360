# 95. Reemplazo de plantilla en el mismo lugar (redeploy estilo KoboToolbox)

## Qué resuelve

Antes de este cambio, importar un archivo XLSForm/SurveyMonkey/LimeSurvey **siempre** creaba una plantilla nueva (`BuilderTemplate` nueva, `template_id` nuevo). No existía forma de "volver a desplegar" un formulario ya publicado conservando su identidad, como sí permite KoboToolbox al reemplazar el formulario de un proyecto existente.

Ahora `POST /xlsform/import` acepta un campo opcional `replace_template_id`: si se envía, el archivo subido reemplaza la estructura de esa plantilla **en el mismo lugar** (mismo `template_id`, mismo nombre, mismo estado, mismo enlace/QR si el formulario está publicado), en vez de crear una plantilla nueva.

## Cómo funciona

1. **Verificación de pertenencia**: si `replace_template_id` no existe o pertenece a otro proyecto, la API responde `404` — nunca se reemplaza una plantilla ajena solo porque alguien adivine su id.
2. **Respaldo automático**: antes de borrar nada, la estructura actual completa (páginas/secciones/filas/columnas/componentes) se guarda como una fila `BuilderVersion` con `status="archived"`, usando el mismo ensamblador que usa Runtime (`runtime_service.build_template_runtime`). Esto reutiliza el modelo `BuilderVersion`, que existía en el código desde antes pero nunca se llegaba a poblar ni a leer.
3. **Reemplazo del contenido visual**: se borran los componentes/columnas/filas/secciones/páginas de la plantilla (la fila de `BuilderTemplate` en sí no se toca), y el importador correspondiente (XLSForm, SurveyMonkey o LimeSurvey — los 3 comparten la misma función `prepare_target_template()` en `form_import_common.py`) la vuelve a poblar con el contenido del archivo nuevo.
4. **Los registros ya capturados no se pierden**: los valores de un `RuntimeRecord` se guardan por `field_name` (texto), no por una referencia estricta a un `BuilderComponent`. Si un campo desaparece de la nueva estructura, sus valores históricos simplemente quedan sin componente visual asociado (dato inerte pero no perdido); los campos que se mantienen con el mismo nombre siguen resolviendo con normalidad.

## Uso

```
POST /api/v1/xlsform/import
Content-Type: multipart/form-data

project_id=<id>
upload=<archivo .xlsx>
replace_template_id=<id de la plantilla a reemplazar>   # opcional
```

Respuesta (`XlsformImportResult`):
```json
{
  "template_id": "...",
  "imported_fields": 12,
  "warnings": [],
  "replaced": true
}
```

`replaced` indica si se reemplazó una plantilla existente (`true`) o se creó una nueva (`false`, comportamiento previo sin cambios).

Funciona igual para los 3 formatos que detecta `form_import_router.detect_format()`: XLSForm, SurveyMonkey y LimeSurvey (ver [docs/94](94_IMPORTADOR_MULTIFORMATO.md)).

## Frontend

En **Importar / exportar XLSForm** (`/admin/xlsform`), el selector "Destino" permite elegir "Crear plantilla nueva" (comportamiento de siempre) o "Reemplazar: <nombre> (<estado>)" para cualquier plantilla existente del proyecto. Al reemplazar, el mensaje de confirmación indica que la estructura anterior quedó respaldada.

## Cómo deshacer (manual, por ahora)

Cada reemplazo deja una fila `BuilderVersion` con `status="archived"` y el `schema_json` completo de la estructura anterior. Todavía no existe un endpoint de "restaurar esta versión" — es la extensión natural de este trabajo si se necesita en el futuro, pero no se construyó porque no fue parte de este pedido. Mientras tanto, restaurar requiere reconstruir manualmente la plantilla a partir de ese JSON.

## Pruebas

`backend/tests/test_template_replace.py` (5 pruebas): reemplazo mantiene el `template_id`, respalda la estructura anterior en `BuilderVersion`, un `RuntimeRecord` capturado antes del reemplazo sobrevive intacto, se rechaza un `replace_template_id` de otro proyecto o inexistente (404), y el flujo funciona también para el formato SurveyMonkey (no solo XLSForm).
