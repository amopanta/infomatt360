# Importador multi-formato (XLSForm + SurveyMonkey + LimeSurvey)

## Objetivo

Que `POST /api/v1/xlsform/import` (la misma pantalla `/admin/xlsform`, sin
un boton nuevo) reconozca automaticamente de que herramienta viene un
archivo `.xlsx` y lo convierta a una plantilla del Builder, sin que el
usuario tenga que indicar el formato manualmente.

## Formatos reconocidos

1. **XLSForm** (ODK/KoboToolbox) — ya existia, ver [docs/81](81_IMPORTADOR_XLSFORM_ODK_KOBO.md) y [docs/93](93_EXPORTADOR_XLSFORM.md). Se detecta por tener una hoja llamada `survey`.
2. **SurveyMonkey** — columnas `Identificador_Pregunta`, `Texto_Pregunta`, `Tipo_Pregunta`, `Opciones_Respuesta_Separadas_Por_Comas`, `Obligatorio` en la primera hoja.
3. **LimeSurvey** — columnas `QuestionCode`, `QuestionText`, `QuestionType`, `AnswerChoices_PipeSeparated`, `IsRequired` en la primera hoja.

La deteccion (`backend/app/services/form_import_router.py::detect_format`) mira primero si hay una hoja `survey` (XLSForm); si no, revisa los encabezados de la primera hoja contra las dos firmas de columnas anteriores. Si no coincide con ninguna, responde `422` con un mensaje que lista las tres formas de columnas aceptadas.

## Nota de honestidad importante

**SurveyMonkey y LimeSurvey no publican un formato de "diseno de encuesta por Excel"** como estandar propio: SurveyMonkey solo exporta *respuestas* (no la definicion de preguntas) a Excel/CSV, y LimeSurvey usa su propio formato binario/XML `.lss`/`.lsg` para estructura de encuestas, no Excel. Las columnas que este importador reconoce (`Identificador_Pregunta`/`Tipo_Pregunta`/... y `QuestionCode`/`QuestionType`/...) son las definidas en la **plantilla de referencia que aporto el usuario** (`plantilla_maestra_formularios_completa.xlsx`, hojas `SurveyMonkey_Template` y `LiveSurvey_Template`), como convencion practica para representar el vocabulario de esas herramientas en un archivo importable — no son el formato nativo real de esas plataformas. Si alguien tiene un archivo exportado *literalmente* de SurveyMonkey o LimeSurvey, es probable que sus columnas no coincidan exactamente y haya que adaptarlas primero a una de estas tres formas reconocidas.

Por la misma razon, **solo se construyo importacion, no exportacion**, a estos dos formatos (alcance confirmado explicitamente): no tiene sentido generar un archivo "estilo SurveyMonkey" cuando esas plataformas no lo consumirian de todas formas. Para llevar un formulario *fuera* de InfoMatt360, usar el exportador XLSForm (docs/93), que si es un estandar real (ODK/KoboToolbox).

## Mapeo de tipos

### SurveyMonkey (`Tipo_Pregunta`, texto descriptivo)

| Texto en la columna | Tipo interno | Nota |
| --- | --- | --- |
| Opción Múltiple (Selección Única) | `SELECT` | opciones desde la columna, separadas por coma |
| Casillas de Verificación (Selección Múltiple) | `MULTISELECT` | idem |
| Cuadro de Texto de Líneas Múltiples | `TEXTAREA` | |
| Cuadro de Texto de una Sola Línea | `TEXT` | |
| Matriz / Escala de Calificación | `MATRIX` | la columna de opciones no se interpreta (formato libre "Filas: ... / Columnas: ..."), queda como advertencia |
| Clasificación / Ranking | `RANKING` | opciones desde la columna |
| Fecha / Hora | `DATETIME` | |
| Net Promoter® Score (NPS) | `NPS` | la columna de opciones se ignora (es un descriptor de escala, no opciones reales) |
| Deslizador / Slider | `RANGE` | intenta leer `Min: X, Max: Y` de la columna de opciones |
| Carga de Archivos | `FILE` | |
| Formulario de Información de Contacto | `TEXT` | campo compuesto (nombre/direccion/telefono) simplificado a un solo texto libre, con advertencia |
| cualquier otro texto | `HIDDEN` | con advertencia de tipo no reconocido |

### LimeSurvey (`QuestionType`, texto descriptivo)

| Texto en la columna | Tipo interno | Nota |
| --- | --- | --- |
| Short Text (Texto Corto) | `TEXT` | |
| Long Text (Texto Largo/Memo) | `TEXTAREA` | |
| Radio Button (Selección Única Horizontal) | `SELECT` | `config.appearance = "horizontal"` |
| Dropdown List (Menú Desplegable) | `DROPDOWN` | |
| Checkboxes (Selección Múltiple) | `MULTISELECT` | |
| Number (Numérico Estricto) | `INTEGER` | |
| Date Picker (Selector de Fecha) | `DATE` | |
| File Upload (Carga de Archivos) | `FILE` | |
| Yes/No Toggle (Botón de Alternancia) | `BOOLEAN` | |
| Star Rating (Calificación con Estrellas) | `RATING` | la columna de opciones se ignora (descriptor de escala) |
| Consent Checkbox (Aceptación de Términos) | `BOOLEAN` | `config.appearance = "consent"`, forzado `required` |
| cualquier otro texto | `HIDDEN` | con advertencia |

Ambos formatos comparten la logica de "opciones no reconocidas se preservan como advertencia" en vez de perderse en silencio (mismo principio que el importador XLSForm, ver docs/81).

## No hay silos por herramienta: composicion libre

Un mismo formulario puede combinar sin restriccion campos que "vienen" de
distintas convenciones -- un `REPEAT` (Kobo), una `MATRIX` (SurveyMonkey),
un `BOOLEAN` con `appearance=consent` (LimeSurvey) y una `REFERENCE`
(ActivityInfo) -- porque todos terminan siendo el mismo tipo de fila
(`BuilderComponent`) dentro de la misma plantilla. Nunca existio una
separacion por "sistema de origen": el catalogo de tipos
(`app.core.field_types`) es unico y el constructor visual y el
importador/exportador XLS leen y escriben exactamente el mismo
`config_json`. Ver `test_combined_form_mixes_field_types_from_every_system_freely`
en `backend/tests/test_multi_format_import.py` para la prueba concreta de
esto.

## Apariencias (`appearance`)

Algunas variantes visuales de un mismo concepto ya son **tipos internos
distintos** (no un atributo `appearance` separado): `TEXT` vs `TEXTAREA`
(una linea vs varias), `SELECT` vs `DROPDOWN` (radio vs menu desplegable),
`RATING`/`LIKERT_5`/`LIKERT_7`/`RANKING` (distintas variantes de escala).

Para las que no ameritan un tipo nuevo, `config.appearance` es un texto
libre que se preserva pero no se interpreta visualmente todavia (se
importa/exporta tal cual, ver docs/93) -- por ejemplo `"horizontal"`
(radio horizontal, estilo LimeSurvey) o `"consent"` (casilla de
consentimiento). La plantilla maestra (`GET /xlsform/master-template`)
incluye un ejemplo de cada uno (`seleccion_horizontal_ejemplo`,
`consentimiento_ejemplo`) para que sirvan de referencia al disenar un
formulario nuevo.

## Verificacion

`backend/tests/test_multi_format_import.py` (5 tests) usa las filas
EXACTAS de la plantilla de referencia del usuario (no datos inventados)
para probar: deteccion de los 3 formatos, importacion completa de la hoja
SurveyMonkey_Template (11 preguntas), importacion completa de la hoja
LiveSurvey_Template (11 preguntas), rechazo `422` con mensaje util para un
archivo de columnas desconocidas, y la prueba de composicion libre
descrita arriba.
