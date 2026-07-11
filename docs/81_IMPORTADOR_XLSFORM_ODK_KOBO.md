# Importador XLSForm (ODK/KoboToolbox)

## Objetivo

Convertir un archivo XLSForm (el estandar de ODK/KoboToolbox para disenar
formularios) en una plantilla equivalente del Builder, para que un equipo
que ya disena formularios en Excel/KoboToolbox pueda migrarlos sin
recrearlos a mano campo por campo.

## Formato de entrada

Un `.xlsx` con dos hojas:

- `survey`: una fila por pregunta, columnas `type`, `name`, `label`
  (los encabezados se detectan de forma flexible: tolera variantes con
  espacios/guiones bajos y coincidencia parcial).
- `choices`: opciones de las preguntas `select_one`/`select_multiple`,
  columnas `list_name`, `name`, `label`.

## Mapeo de tipos

Reutiliza el catalogo de tipos ya existente
(`app.core.field_types.normalize_field_type`), que ya acepta los nombres de
XLSForm en minuscula. Los casos con manejo especial en el importador:

| Tipo XLSForm | Resultado |
| --- | --- |
| `select_one <lista>` / `select_multiple <lista>` | Componente `SELECT`/`MULTISELECT` con las opciones de la hoja `choices` |
| `begin_group` / `end_group` | Se aplanan (no generan un componente propio) |
| `begin_repeat` / `end_repeat` | Se agrupan en un solo componente `REPEAT`, con los campos anidados guardados en `config_json` |
| `note`, `start`, `end`, `today`, `deviceid`, `subscriberid`, `simserial`, `username`, `audit`, `text-audit`, `calculate_here` | Se omiten (metadatos de ODK sin campo visible equivalente) |
| Tipo desconocido sin equivalente | Se importa como campo `HIDDEN` y se agrega una advertencia |

## Endpoint

`POST /api/v1/xlsform/import` (permiso `builder.write`) — recibe
`project_id` (form field) y el archivo (`multipart/form-data`). Crea la
plantilla Builder completa (`BuilderTemplate` + una pagina + una seccion
con todos los campos) en una sola llamada y devuelve
`{ template_id, imported_fields, warnings[] }`.

## Advertencias, no errores duros

El importador prefiere seguir con advertencias en vez de abortar la
importacion completa: una lista de opciones faltante, un tipo sin
equivalente directo o un `end_repeat` sin `begin_repeat` no detienen el
proceso — el resultado incluye el detalle en `warnings[]` para que el
administrador revise y corrija manualmente los campos senalados despues de
importar.

## Limites conocidos

- No importa `relevant` (logica condicional de XLSForm) ni `constraint`
  (validaciones); estas reglas deben recrearse manualmente en el Builder
  despues de importar.
- Requiere que la hoja `survey` tenga al menos las columnas `type` y
  `name`; si faltan, la importacion completa se rechaza con `422`.
