# JSON Schema Interno de Formularios

## Objetivo
Definir una estructura unica para que Web, Android, Desktop, PDF, IA y reportes interpreten el mismo formulario.

## Estructura base

```json
{
  "templateId": "tpl-001",
  "version": 1,
  "pages": [
    {
      "title": "Informacion General",
      "sections": [
        {
          "title": "Datos Basicos",
          "rows": [
            {
              "columns": [
                {
                  "desktopWidth": 6,
                  "tabletWidth": 12,
                  "mobileWidth": 12,
                  "components": []
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## Principios

- un solo schema para todos los canales;
- layout libre y responsive;
- versionado obligatorio;
- no crear tablas fisicas por formulario;
- compatibilidad futura con XLSForm import/export.

## Pendientes

- agregar reglas;
- agregar componentes por columna;
- agregar formulas;
- agregar version publicada;
- agregar validaciones de schema.
