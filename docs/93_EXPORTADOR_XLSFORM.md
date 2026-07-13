# Exportador XLSForm (.xlsx) + plantilla maestra

## Objetivo

Operacion inversa de [docs/81](81_IMPORTADOR_XLSFORM_ODK_KOBO.md): convertir
cualquier plantilla del Builder (disenada a mano o importada desde
XLSForm) en un archivo `.xlsx` compatible con KoboToolbox/ODK, para que un
equipo pueda llevarse un formulario fuera de InfoMatt360, auditarlo en
Excel, o crear/reemplazar formularios masivamente subiendo un Excel (igual
que en KoboToolbox).

Alcance explicito: solo XLS/XLSForm, no XML/XForm. InfoMatt360 no compila
a XForm porque el Runtime consume su propio JSON, no XForm.

## Formato de salida

Un `.xlsx` con dos hojas, generado con `openpyxl`:

- `survey`: columnas `type`, `name`, `label`, `hint`, `required`,
  `relevant`, `constraint`, `constraint_message`, `appearance`,
  `parameters` — una fila por campo (recorre el arbol paginas -> secciones
  -> filas -> columnas -> componentes vía
  `runtime_service.build_template_runtime()` y lo aplana en una sola
  hoja).
- `choices`: columnas `list_name`, `name`, `label`, generada solo para los
  campos que la necesitan.

Estas columnas no son metadatos decorativos: se sintetizan desde las
mismas claves de `config_json` que ya usa/entiende el constructor visual
(`placeholder`, `required`, `relevant`, `pattern`/`min`/`max`/
`min_length`/`max_length`), asi que abrir el archivo en Excel y editar
`hint`/`required`/`constraint` tiene efecto real al reimportarlo.

## Mapeo de tipos

Tabla exhaustiva en `EXPORT_TYPE_MAP`
(`backend/app/services/xlsform_export_service.py`) para los tipos con
equivalente directo (`TEXT`→`text`, `NUMBER`/`INTEGER`→`integer`,
`GPS`→`geopoint`, `DATE`→`date`, `RANGE`→`range`, etc.). Cualquier tipo
nuevo que se agregue a `app.core.field_types` sin actualizar el mapa cae
en el fallback `"text"` — la exportacion nunca falla por un tipo
desconocido (verificado con un assert al importar el modulo: la plantilla
maestra debe cubrir el 100% del catalogo).

Casos con logica especial:

| Tipo interno | Resultado en XLSForm |
| --- | --- |
| `SELECT` / `MULTISELECT` / `DROPDOWN` | `select_one`/`select_multiple <lista>` + hoja `choices` con las opciones del componente |
| `RANKING` | `rank <lista>` + hoja `choices` (importa/exporta el alias `rank` de ODK) |
| `BOOLEAN` (incluye el alias `acknowledge` de ODK) | `select_one yes_no`, con una lista `yes_no` (Sí/No) compartida entre todos los campos booleanos |
| `LIKERT_5` / `LIKERT_7` | `select_one <nombre>`, con una lista numerica 1-5 o 1-7 autogenerada |
| `RANGE` | `range`, con la columna `parameters` (`start=<min> end=<max> step=<step>`) |
| `REPEAT` | `begin_repeat`/`end_repeat` desenrollando los campos anidados guardados en `config_json` (mismo formato que produce el importador) |

## Columnas comunes (hint, required, relevant, constraint)

- `hint` ↔ `config.placeholder`.
- `required` ↔ `config.required` (`"yes"` si es verdadero, vacio si no).
- `relevant` (logica condicional) ↔ `config.relevant` (`{field, operator,
  value}`, el mismo formato que ya usa el selector "Mostrar si..." del
  constructor visual). Se reconocen los patrones `${campo} = 'valor'`,
  `!=`, `!= ''` (`not_empty`) y `= ''` (`empty`).
- `constraint` (validacion) ↔ `config.pattern`/`min`/`max`/`min_length`/
  `max_length`. Se reconocen `regex(., '...')`, `. >= N`, `. <= N`,
  `string-length(.) >= N` y `string-length(.) <= N`, combinables con
  `and`.
- Si una expresion `relevant`/`constraint` importada no coincide con
  ninguno de estos patrones (por ejemplo, una expresion con `selected()`
  o comparaciones entre dos campos), el importador **preserva el texto
  original** en `config.relevant_expression`/`config.constraint_expression`
  y agrega una advertencia — no se activa como condicion/validacion real
  en el Runtime, pero tampoco se pierde: al volver a exportar el campo, se
  reescribe la expresion tal cual, garantizando un round-trip fiel para
  ese texto aunque no sea interpretable.

## Endpoints

- `GET /api/v1/xlsform/export/{template_id}` (permiso `builder.write`,
  validado contra el proyecto dueno de la plantilla) — responde el archivo
  `.xlsx` de esa plantilla como `attachment`.
- `GET /api/v1/xlsform/master-template?project_id=...` (permiso
  `builder.write` sobre ese proyecto) — responde una plantilla de
  referencia (`plantilla_maestra_infomatt360.xlsx`) con **un campo de
  ejemplo por cada uno de los tipos soportados** (texto, numericos,
  fecha/hora, seleccion unica/multiple/lista desplegable, ranking,
  deslizador, medios, GPS, repetibles, calculo, y ejemplos de
  `hint`/`required`/`relevant`/`constraint`), pensada para descargarla,
  editarla en Excel y subirla de vuelta — el mismo flujo de "formulario
  maestro" de KoboToolbox/ActivityInfo/SurveyMonkey/LimeSurvey que unifica
  create-rapido-por-Excel + reemplazo de formularios existentes.

## Pantalla

`/admin/xlsform` (frontend) combina en una sola pantalla el importador
existente (antes sin UI propia, solo accesible por API), el botón para
descargar la plantilla maestra, y el exportador de cualquier plantilla del
proyecto.

## Limites conocidos

- Exportacion best-effort, no round-trip perfecto para tipos sin
  equivalente en XLSForm (`UUID`, `RESPONSE_ID`, `CAPTURED_BY`, etc. caen
  en `calculate`/`text` segun el mapa).
- `relevant`/`constraint` solo se traducen a condiciones/validaciones
  activas para los patrones simples descritos arriba (campo unico
  comparado con un literal, rango numerico, regex, longitud de texto).
  Expresiones mas complejas (comparaciones entre dos campos,
  `selected()`, funciones XPath anidadas) se preservan como texto pero no
  se interpretan.
- No se soportan `trigger`, `choice_filter` (listas en cascada) ni
  `repeat_count` como columnas activas; tampoco los tipos
  `csv-external`/`xml-external` (fuentes de datos externas) ni `audit`
  (bitacora de auditoria de ODK) — se importan como campo oculto con
  advertencia o se omiten como metadato, segun el caso.
- La estructura de paginas/secciones del Builder se pierde al aplanar a
  una sola hoja `survey` (misma limitacion, simetrica, que el importador).
- La deteccion es exclusiva para el formato XLSForm (hojas `survey`/
  `choices`); no se reconocen los formatos propios de otras herramientas
  (ActivityInfo, SurveyMonkey, LimeSurvey) si no vienen ya convertidos a
  XLSForm.

## Verificacion

- `backend/tests/test_xlsform_export.py`: permisos, 404 de plantilla
  inexistente, contenido del workbook (tipos, hoja `choices`, repeat
  anidado), round-trip completo del caso basico, round-trip de las
  columnas enriquecidas (hint/required/relevant/constraint/range/rank), y
  la plantilla maestra (permisos + cobertura del 100% del catalogo de
  tipos + reimportacion sin advertencias).
- `backend/tests/test_xlsform_import.py`: mapeo de columnas enriquecidas,
  y preservacion de expresiones `relevant`/`constraint` no reconocidas.
- Verificado ademas contra el servidor real (no solo el TestClient de
  pytest): login real, descarga del `.xlsx` de la plantilla demo
  (`demo-template-characterization`), y reimportacion de esos mismos
  bytes vía una peticion `multipart/form-data` real contra
  `POST /xlsform/import` — resultado `200` con los 4 campos y
  `warnings: []`.
