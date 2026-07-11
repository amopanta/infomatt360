"""Generador de actas/documentos PDF a partir de plantillas HTML+Jinja2.

Usa `xhtml2pdf` (basado en reportlab, sin dependencias nativas) en vez de
WeasyPrint: WeasyPrint requiere librerias GTK/Pango que no estan disponibles
en todos los entornos Windows de desarrollo. xhtml2pdf cubre el caso de uso
(actas con texto, tablas, logo e imagenes) sin esa fragilidad.
"""

import io

import jinja2
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from xhtml2pdf import pisa

from app.core.time import utc_now
from app.models.acta import ActaTemplate
from app.schemas.acta import ActaTemplateCreate, ActaTemplateRead

_jinja_env = jinja2.Environment(autoescape=True)


def _to_read(row: ActaTemplate) -> ActaTemplateRead:
    return ActaTemplateRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        html_template=row.html_template,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ActaService:
    def create_template(self, db: Session, payload: ActaTemplateCreate) -> ActaTemplateRead:
        row = ActaTemplate(project_id=payload.project_id, name=payload.name, html_template=payload.html_template)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def list_templates(self, db: Session, project_id: str) -> list[ActaTemplateRead]:
        rows = db.query(ActaTemplate).filter(ActaTemplate.project_id == project_id).order_by(ActaTemplate.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def get_template(self, db: Session, template_id: str) -> ActaTemplate | None:
        return db.query(ActaTemplate).filter(ActaTemplate.id == template_id).first()

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
            return _jinja_env.from_string(template.html_template).render(**data)
        except jinja2.TemplateError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Plantilla invalida: {exc}") from exc

    def render_pdf(self, template: ActaTemplate, data: dict[str, str]) -> bytes:
        compiled_html = self.render_html(template, data)
        buffer = io.BytesIO()
        result = pisa.CreatePDF(compiled_html, dest=buffer, encoding="utf-8")
        if result.err:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No fue posible generar el PDF a partir de la plantilla")
        return buffer.getvalue()


acta_service = ActaService()
