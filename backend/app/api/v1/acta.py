from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.acta import ActaLayoutTemplateCreate, ActaRenderFromRecordRequest, ActaRenderRequest, ActaTemplateCreate, ActaTemplateRead
from app.services.acta_service import acta_service
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.post("/", response_model=ActaTemplateRead, summary="Crear plantilla de acta")
def create_acta_template(payload: ActaTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ActaTemplateRead:
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return acta_service.create_template(db, payload)


@router.get("/project/{project_id}", response_model=list[ActaTemplateRead], summary="Listar plantillas de acta por proyecto")
def list_acta_templates(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ActaTemplateRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return acta_service.list_templates(db, project_id)


@router.put("/{template_id}", response_model=ActaTemplateRead, summary="Editar plantilla de acta")
def update_acta_template(template_id: str, payload: ActaTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ActaTemplateRead:
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return acta_service.update_template(db, template_id, payload)


@router.post("/{template_id}/render", summary="Generar PDF a partir de la plantilla")
def render_acta_pdf(template_id: str, payload: ActaRenderRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    template = acta_service.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla de acta no encontrada")
    if not assignment_service.user_has_project_access(db, current_user.id, template.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    pdf_bytes = acta_service.render_pdf(template, payload.data)
    return _pdf_response(pdf_bytes, template.name)


@router.post("/layout", response_model=ActaTemplateRead, summary="Crear plantilla de acta (constructor visual)")
def create_acta_layout_template(payload: ActaLayoutTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ActaTemplateRead:
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return acta_service.create_layout_template(db, payload)


@router.put("/{template_id}/layout", response_model=ActaTemplateRead, summary="Editar plantilla de acta (constructor visual)")
def update_acta_layout_template(template_id: str, payload: ActaLayoutTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ActaTemplateRead:
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return acta_service.update_layout_template(db, template_id, payload)


@router.post("/{template_id}/render-from-record", summary="Generar PDF a partir de un registro (constructor visual)")
def render_acta_from_record(template_id: str, payload: ActaRenderFromRecordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    template = acta_service.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla de acta no encontrada")
    if not assignment_service.user_has_project_access(db, current_user.id, template.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    pdf_bytes = acta_service.render_pdf_from_record(db, template, payload.record_id)
    return _pdf_response(pdf_bytes, template.name)


def _pdf_response(pdf_bytes: bytes, template_name: str) -> Response:
    safe_name = "".join(character if character.isascii() and (character.isalnum() or character in "-_") else "_" for character in template_name).strip("_") or "acta"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'},
    )
