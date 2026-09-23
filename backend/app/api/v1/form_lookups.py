"""Manage and query KoBo-compatible pulldata CSVs."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.builder_access import require_template_access
from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.form_lookup import FormLookup
from app.models.identity import User
from app.services.auth_throttle_service import auth_throttle_service
from app.services.builder_public_link_service import builder_public_link_service
from app.services.form_lookup_service import lookup_value, put_lookup, referenced_lookup

router = APIRouter()


class LookupInfo(BaseModel):
    name: str
    row_count: int
    columns: list[str]
    checksum: str


class LookupResult(BaseModel):
    value: str


class LookupRequest(BaseModel):
    file: str
    column: str
    key_column: str
    key: str


def info(item: FormLookup) -> LookupInfo:
    import json
    return LookupInfo(name=item.name, row_count=item.row_count, columns=json.loads(item.columns_json), checksum=item.checksum)


@router.get("/templates/{template_id}", response_model=list[LookupInfo])
def list_lookups(template_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_template_access(db, user.id, template_id)
    return [info(item) for item in db.query(FormLookup).filter(FormLookup.template_id == template_id).order_by(FormLookup.name).all()]


@router.post("/templates/{template_id}", response_model=LookupInfo)
async def upload_lookup(template_id: str, upload: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = require_template_access(db, user.id, template_id)
    require_project_permission(db, user.id, template.project_id, BUILDER_WRITE)
    content = await upload.read(5 * 1024 * 1024 + 1)
    return info(put_lookup(db, template.project_id, template_id, upload.filename or "", content))


@router.post("/templates/{template_id}/value", response_model=LookupResult)
def private_lookup(template_id: str, payload: LookupRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_template_access(db, user.id, template_id)
    return LookupResult(value=lookup_value(db, template_id, payload.file, payload.column, payload.key_column, payload.key))


@router.post("/public/{token}/value", response_model=LookupResult)
def public_lookup(token: str, payload: LookupRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if auth_throttle_service.is_blocked(db, "pulldata-ip", ip):
        raise HTTPException(status_code=429, detail="Demasiadas consultas")
    try:
        link = builder_public_link_service.validate_token(db, token)
    except ValueError as exc:
        auth_throttle_service.record_attempt(db, "pulldata-ip", ip, maximum=30, window_minutes=15, block_minutes=15)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not auth_throttle_service.record_attempt(db, "pulldata-query-ip", ip, maximum=300, window_minutes=15, block_minutes=15):
        raise HTTPException(status_code=429, detail="Demasiadas consultas")
    if not referenced_lookup(db, link.template_id, payload.file, payload.column, payload.key_column):
        raise HTTPException(status_code=403, detail="Esta consulta no está definida en el formulario")
    return LookupResult(value=lookup_value(db, link.template_id, payload.file, payload.column, payload.key_column, payload.key))
