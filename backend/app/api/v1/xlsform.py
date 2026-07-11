from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.xlsform import XlsformImportResult
from app.services.xlsform_import_service import xlsform_import_service

router = APIRouter()


@router.post("/import", response_model=XlsformImportResult, summary="Importar plantilla XLSForm (ODK/KoboToolbox)")
async def import_xlsform(
    project_id: str = Form(...),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> XlsformImportResult:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = await upload.read()
    return xlsform_import_service.import_xlsform(db, project_id, upload.filename or "formulario.xlsx", content, current_user.id)
