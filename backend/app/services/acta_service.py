"""Generador de actas/documentos PDF.

Dos caminos de renderizado (ver el docstring de `app.models.acta.ActaTemplate`
y docs/109 para el detalle completo):

- Legado: `render_html`/`render_pdf` compilan `template.html_template`
  (Jinja2 crudo) con un `data: dict[str, str]` provisto por el llamador.
- Constructor visual: `render_html_from_blocks`/`render_pdf_from_record`
  arman el HTML a partir de bloques estructurados (`layout_json`) resueltos
  contra un `RuntimeRecord` real, sin exponer Jinja2 crudo al usuario.

Ambos caminos comparten `_html_to_pdf_bytes`, que usa `xhtml2pdf` (basado en
reportlab, sin dependencias nativas) en vez de WeasyPrint: WeasyPrint
requiere librerias GTK/Pango que no estan disponibles en todos los entornos
Windows de desarrollo. xhtml2pdf cubre el caso de uso (actas con texto,
tablas, logo e imagenes) sin esa fragilidad.
"""

import csv
import html
import io
import json
import re
import zipfile

import jinja2
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from xhtml2pdf import pisa

from app.core.time import utc_now
from app.models.builder import BuilderComponent
from app.models.acta import ActaTemplate
from app.models.identity import Project
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.acta import ActaLayout, ActaLayoutTemplateCreate, ActaTemplateCreate, ActaTemplateRead
from app.services.organization_service import organization_service

_jinja_env = jinja2.Environment(autoescape=True)

_TOKEN_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _to_read(row: ActaTemplate) -> ActaTemplateRead:
    return ActaTemplateRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        html_template=row.html_template,
        layout_json=row.layout_json,
        template_id=row.template_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _decode_value_for_display(field_value_json: str) -> str:
    """Convierte un valor capturado (JSON) a texto legible para una celda de
    tabla del acta. No intenta replicar todo el formateo rico del frontend
    (GPS, listas, firmas) -- solo evita mostrar JSON crudo para los tipos
    compuestos mas comunes."""
    try:
        value = json.loads(field_value_json)
    except json.JSONDecodeError:
        return field_value_json
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(_decode_value_for_display(json.dumps(item)) for item in value)
    if isinstance(value, dict):
        if "coordinates" in value and "type" in value:  # GeoJSON point/geometria
            return str(value.get("coordinates"))
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _html_to_pdf_bytes(compiled_html: str) -> bytes:
    buffer = io.BytesIO()
    result = pisa.CreatePDF(compiled_html, dest=buffer, encoding="utf-8")
    if result.err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No fue posible generar el PDF a partir de la plantilla")
    return buffer.getvalue()


def _manifest_csv(rows: list[tuple[str, str, str]]) -> str:
    output = io.StringIO()
    output.write("﻿")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    return output.getvalue()


class ActaService:
    # --- Camino legado (Jinja2 crudo, sin UI) ---

    def create_template(self, db: Session, payload: ActaTemplateCreate) -> ActaTemplateRead:
        row = ActaTemplate(project_id=payload.project_id, name=payload.name, html_template=payload.html_template)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def update_template(self, db: Session, template_id: str, payload: ActaTemplateCreate) -> ActaTemplateRead:
        row = self.get_template(db, template_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla de acta no encontrada")
        row.name = payload.name
        row.html_template = payload.html_template
        row.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def render_html(self, template: ActaTemplate, data: dict[str, str]) -> str:
        """Compila la plantilla con los datos, escapando HTML para evitar que
        un dato de entrada rompa la estructura del acta (inyeccion de marcado)."""
        try:
            return _jinja_env.from_string(template.html_template or "").render(**data)
        except jinja2.TemplateError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Plantilla invalida: {exc}") from exc

    def render_pdf(self, template: ActaTemplate, data: dict[str, str]) -> bytes:
        return _html_to_pdf_bytes(self.render_html(template, data))

    # --- Comunes a ambos caminos ---

    def list_templates(self, db: Session, project_id: str) -> list[ActaTemplateRead]:
        rows = db.query(ActaTemplate).filter(ActaTemplate.project_id == project_id).order_by(ActaTemplate.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def get_template(self, db: Session, template_id: str) -> ActaTemplate | None:
        return db.query(ActaTemplate).filter(ActaTemplate.id == template_id).first()

    # --- Constructor visual ---

    def create_layout_template(self, db: Session, payload: ActaLayoutTemplateCreate) -> ActaTemplateRead:
        row = ActaTemplate(
            project_id=payload.project_id,
            name=payload.name,
            template_id=payload.template_id,
            layout_json=payload.layout.model_dump_json(),
            html_template=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def update_layout_template(self, db: Session, template_id: str, payload: ActaLayoutTemplateCreate) -> ActaTemplateRead:
        row = self.get_template(db, template_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla de acta no encontrada")
        if row.html_template is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Esta plantilla usa el camino legado (HTML crudo) y no se puede editar con el constructor visual")
        row.name = payload.name
        row.template_id = payload.template_id
        row.layout_json = payload.layout.model_dump_json()
        row.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def render_html_from_blocks(self, db: Session, template: ActaTemplate, record_id: str) -> str:
        if not template.layout_json or not template.template_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Esta plantilla usa el camino legado (HTML crudo); use POST /{id}/render en su lugar")

        record = db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id).first()
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
        if record.template_id != template.template_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El registro no pertenece a la plantilla de formulario para la que se diseño esta acta")

        values = {
            item.field_name: _decode_value_for_display(item.field_value_json)
            for item in db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record_id).all()
        }
        labels = {
            component.name: component.label
            for component in db.query(BuilderComponent).filter(BuilderComponent.template_id == template.template_id).all()
        }

        branding = None
        project = db.query(Project).filter(Project.id == template.project_id).first()
        if project and project.organization_id:
            branding = organization_service.get_branding(db, project.organization_id)

        layout = ActaLayout.model_validate_json(template.layout_json)
        body_parts: list[str] = []
        for block in layout.blocks:
            if block.type == "logo":
                if branding and branding.logo_url:
                    align = html.escape(block.alignment)
                    body_parts.append(f'<div style="text-align:{align}"><img src="{html.escape(branding.logo_url)}" style="max-height:80px"></div>')
                else:
                    body_parts.append("<!-- bloque logo: sin logo configurado en la organizacion -->")
            elif block.type == "header":
                try:
                    resolved_text = _jinja_env.from_string(block.text).render(**values)
                except jinja2.TemplateError as exc:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Encabezado invalido: {exc}") from exc
                body_parts.append(f"<h{block.level}>{resolved_text}</h{block.level}>")
            elif block.type == "table":
                rows_html = "".join(
                    f"<tr><td><strong>{html.escape(labels.get(field_name, field_name))}</strong></td><td>{html.escape(values.get(field_name, '-'))}</td></tr>"
                    for field_name in block.field_names
                )
                body_parts.append(f'<table style="width:100%;border-collapse:collapse" border="1" cellpadding="6">{rows_html}</table>')
            elif block.type == "signature":
                body_parts.append(f'<div class="acta-signature-line" style="margin-top:40px">____________________<br>{html.escape(block.label)}</div>')

        body = "\n".join(body_parts)
        return f'<html><head><meta charset="utf-8"><style>body {{ font-family: Helvetica, Arial, sans-serif; margin: 32px; }} table td {{ padding: 4px; }}</style></head><body>{body}</body></html>'

    def render_pdf_from_record(self, db: Session, template: ActaTemplate, record_id: str) -> bytes:
        return _html_to_pdf_bytes(self.render_html_from_blocks(db, template, record_id))

    def render_pdf_batch(self, db: Session, template: ActaTemplate, record_ids: list[str]) -> bytes:
        """Genera un ZIP con un PDF por registro (docs/96 item #5). Reusa
        render_pdf_from_record sin cambios; un fallo individual no aborta el
        lote -- se anota en manifest.csv, mismo espiritu 'por item' que el
        guardado masivo de registros (save_records_bulk)."""
        buffer = io.BytesIO()
        manifest: list[tuple[str, str, str]] = [("record_id", "status", "error")]
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for record_id in record_ids:
                try:
                    pdf_bytes = self.render_pdf_from_record(db, template, record_id)
                    archive.writestr(f"{record_id}.pdf", pdf_bytes)
                    manifest.append((record_id, "success", ""))
                except HTTPException as exc:
                    manifest.append((record_id, "failed", str(exc.detail)))
            archive.writestr("manifest.csv", _manifest_csv(manifest))
        return buffer.getvalue()


acta_service = ActaService()
