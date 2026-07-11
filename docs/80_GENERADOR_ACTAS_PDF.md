# Generador de actas PDF

## Objetivo

Generar documentos PDF (actas, constancias) a partir de plantillas HTML con
marcadores Jinja2, disenadas por un coordinador del proyecto y compiladas
con datos reales al momento de generar el PDF.

## Por que xhtml2pdf y no WeasyPrint

WeasyPrint (la opcion inicialmente evaluada) requiere librerias nativas
GTK/Pango que no estan disponibles en todos los entornos Windows de
desarrollo, y su instalacion fallaba de forma no trivial. `xhtml2pdf`
(basado en `reportlab`) no tiene dependencias nativas y cubre el caso de
uso (texto, tablas, logo, imagenes) sin esa fragilidad.

## Modelo

`ActaTemplate` (`backend/app/models/acta.py`): `project_id`, `name`,
`html_template` (el HTML con marcadores `{{ campo }}`), `created_at`,
`updated_at`. No hay tabla por PDF generado: el archivo se transmite en
streaming (`Response` con `media_type="application/pdf"`) y no se persiste
en el servidor.

## Seguridad: autoescape forzado

`acta_service.py` crea el entorno Jinja2 con `autoescape=True`
**incondicional** (`jinja2.Environment(autoescape=True)`), no
`select_autoescape` (que detecta por extension de archivo — no aplica aqui
porque la plantilla viene de un string en base de datos, no de un archivo
`.html`). Esto evita que un dato de entrada con HTML/JS incrustado rompa la
estructura del documento o inyecte marcado en el PDF generado.

## Endpoints

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/api/v1/acta-templates/` | `builder.write` |
| `GET` | `/api/v1/acta-templates/project/{project_id}` | acceso al proyecto |
| `PUT` | `/api/v1/acta-templates/{template_id}` | `builder.write` |
| `POST` | `/api/v1/acta-templates/{template_id}/render` | acceso al proyecto |

`render` devuelve el PDF como adjunto (`Content-Disposition: attachment`);
el nombre de archivo se sanitiza (solo ASCII alfanumerico, `-`, `_`) para
evitar inyeccion de headers HTTP a traves del nombre de la plantilla.

## Limites conocidos

- Sin editor visual de plantillas en el frontend todavia: la plantilla HTML
  se crea/edita como texto plano via API.
- `xhtml2pdf` soporta un subconjunto de CSS (no todo CSS3 moderno); disenos
  complejos pueden requerir simplificar el HTML de la plantilla.
