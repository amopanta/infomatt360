import json
import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pypdf.errors import PdfReadError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.builder_access import require_column_access, require_template_access, template_id_for_column
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE, IDENTITY_USERS_MANAGE
from app.models.audit import AuditLog
from app.db.session import get_db
from app.models.identity import User
from app.models.builder import BuilderComponent, BuilderTemplate
from app.schemas.builder import BuilderComponentCreate, BuilderComponentPropertiesUpdate, BuilderComponentRead, BuilderTemplateCreate, BuilderTemplatePropertiesUpdate, BuilderTemplateRead, BuilderTemplateScheduleUpdate, BuilderTemplateStatusUpdate, BuilderVersionCreate, BuilderVersionRead, ParticipantSourceUpdate
from app.services.participant_source_service import eligible_participants
from app.schemas.participants import ParticipantRead
from app.services.participant_service import _to_read as participant_to_read
from app.services.assignment_service import assignment_service
from app.services.builder_service import builder_service
from app.services.pdf_form_suggestion_service import suggest_pdf_questions
from app.services.ai_audit_service import ai_audit_service, _extract_json_object

router = APIRouter()


class AiQuestionRequest(BaseModel):
    project_id: str
    description: str


@router.post("/assist/ai-questions")
async def preview_ai_questions(
    payload: AiQuestionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
) -> dict:
    """Propone preguntas editables; nunca guarda ni publica una plantilla."""
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    description = payload.description.strip()
    if not 20 <= len(description) <= 4000:
        raise HTTPException(status_code=422, detail="Describe el formulario en 20 a 4000 caracteres")
    if not ai_audit_service.is_configured():
        raise HTTPException(status_code=503, detail="El proveedor de IA aún no está configurado en el servidor")
    prompt = (
        "Diseña hasta 20 preguntas para un formulario de captura. Responde SOLO un objeto JSON "
        "con la clave questions, una lista de objetos con label y type. Tipos permitidos: "
        "TEXT, NUMBER, DATE, EMAIL, PHONE, SELECT, BOOLEAN. No inventes datos personales. "
        "Descripción: " + description
    )
    try:
        raw = await asyncio.to_thread(ai_audit_service._call_llm, prompt)
        parsed = _extract_json_object(raw)
        allowed = {"TEXT", "NUMBER", "DATE", "EMAIL", "PHONE", "SELECT", "BOOLEAN"}
        questions = [
            {"label": item["label"].strip()[:180], "type": item["type"].upper()}
            for item in parsed.get("questions", [])[:20]
            if isinstance(item, dict) and isinstance(item.get("label"), str)
            and isinstance(item.get("type"), str) and item["type"].upper() in allowed
            and item["label"].strip()
        ]
        if not questions:
            raise ValueError("El proveedor no devolvió preguntas válidas")
        return {"questions": questions}
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="El proveedor de IA no respondió. Intenta más tarde") from exc


@router.post("/assist/pdf-questions")
async def preview_pdf_questions(
    project_id: str = Form(...), upload: UploadFile = File(...),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
) -> dict:
    """Propone preguntas para revisión; no crea ni publica un formulario."""
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    if not (upload.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Selecciona un archivo PDF")
    content = await upload.read(5_000_001)
    if len(content) > 5_000_000:
        raise HTTPException(status_code=413, detail="El PDF supera 5 MB")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="El archivo no es un PDF válido")
    try:
        return suggest_pdf_questions(content)
    except (PdfReadError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class TemplateDeleteConfirmation(BaseModel):
    name: str


@router.post("/templates", response_model=BuilderTemplateRead)
def create_template(payload: BuilderTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    """Crea una plantilla visual dentro de un proyecto autorizado."""
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return builder_service.create_template(db, payload, current_user.id)


@router.get("/templates/{project_id}", response_model=list[BuilderTemplateRead])
def list_templates(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderTemplateRead]:
    """Lista las plantillas visuales de un proyecto autorizado."""
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return builder_service.list_templates(db, project_id)


@router.get("/templates/detail/{template_id}", response_model=BuilderTemplateRead)
def get_template_detail(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    require_template_access(db, current_user.id, template_id)
    return builder_service.get_template(db, template_id)


@router.post("/templates/detail/{template_id}/delete")
def delete_template(template_id: str, payload: TemplateDeleteConfirmation, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, IDENTITY_USERS_MANAGE)
    if payload.name.strip() != template.name:
        raise HTTPException(status_code=422, detail="Escribe el nombre exacto del formulario para confirmar")
    before = {"name": template.name, "status": template.status}
    template.status = "deleted"
    from app.core.time import utc_now
    template.updated_at = utc_now()
    db.add(AuditLog(project_id=template.project_id, user_id=current_user.id, module="builder",
                    action="delete_template", entity_type="builder_template", entity_id=template.id,
                    before_json=json.dumps(before, ensure_ascii=False),
                    after_json=json.dumps({"status": "deleted"})))
    db.commit()
    return {"deleted": True}


@router.post("/templates/detail/{template_id}/duplicate", response_model=BuilderTemplateRead)
def duplicate_template(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.duplicate_template(db, template_id, current_user.id)


@router.patch("/templates/detail/{template_id}/status", response_model=BuilderTemplateRead)
def update_template_status(template_id: str, payload: BuilderTemplateStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_template_status(db, template_id, payload.status)


@router.patch("/templates/detail/{template_id}/properties", response_model=BuilderTemplateRead)
def update_template_properties(template_id: str, payload: BuilderTemplatePropertiesUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_template_properties(db, template_id, payload)


@router.patch("/templates/detail/{template_id}/schedule", response_model=BuilderTemplateRead)
def update_template_schedule(template_id: str, payload: BuilderTemplateScheduleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_template_schedule(db, template_id, payload.starts_at, payload.ends_at)


@router.patch("/templates/detail/{template_id}/participant-source", response_model=BuilderTemplateRead)
def update_participant_source(template_id: str, payload: ParticipantSourceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderTemplateRead:
    template = require_template_access(db, current_user.id, template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_participant_source(db, template_id, payload.source)


@router.get("/templates/detail/{template_id}/eligible-participants", response_model=list[ParticipantRead])
def get_eligible_participants(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantRead]:
    template = require_template_access(db, current_user.id, template_id)
    return [participant_to_read(item) for item in eligible_participants(db, template, current_user.id)]


@router.post("/components", response_model=BuilderComponentRead)
def add_component(payload: BuilderComponentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderComponentRead:
    """Agrega un componente o campo a una plantilla.

    El campo puede quedar asociado a una columna para que el Runtime lo ubique
    correctamente dentro del layout responsive.
    """
    require_template_access(db, current_user.id, payload.template_id)
    if payload.column_id:
        column = require_column_access(db, current_user.id, payload.column_id)
        if template_id_for_column(db, column) != payload.template_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La columna no pertenece a la plantilla")
    return builder_service.add_component(db, payload)


@router.get("/components/{template_id}", response_model=list[BuilderComponentRead])
def list_components(template_id: str, column_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderComponentRead]:
    """Lista componentes de una plantilla, opcionalmente por columna."""
    require_template_access(db, current_user.id, template_id)
    if column_id:
        column = require_column_access(db, current_user.id, column_id)
        if template_id_for_column(db, column) != template_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La columna no pertenece a la plantilla")
    return builder_service.list_components(db, template_id, column_id)


@router.patch("/components/detail/{component_id}", response_model=BuilderComponentRead)
def update_component_properties(component_id: str, payload: BuilderComponentPropertiesUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderComponentRead:
    component = db.get(BuilderComponent, component_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    template = require_template_access(db, current_user.id, component.template_id)
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_service.set_component_properties(db, component_id, payload)


@router.post("/versions", response_model=BuilderVersionRead)
def create_version(payload: BuilderVersionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderVersionRead:
    """Guarda una version JSON de una plantilla."""
    require_template_access(db, current_user.id, payload.template_id)
    return builder_service.create_version(db, payload)
