from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.ai import AiCheckCreate, AiCheckRead, ExecutiveAnalysisCreate, ExecutiveAnalysisRead, OcrResultCreate, OcrResultRead
from app.services.ai_service import ai_service
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.post("/checks", response_model=AiCheckRead)
def create_check(payload: AiCheckCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AiCheckRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return ai_service.create_check(db, payload, current_user.id)


@router.get("/checks/{project_id}", response_model=list[AiCheckRead])
def list_checks(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[AiCheckRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return ai_service.list_checks(db, project_id)


@router.post("/ocr", response_model=OcrResultRead)
def create_ocr(payload: OcrResultCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> OcrResultRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return ai_service.create_ocr(db, payload)


@router.post("/analysis", response_model=ExecutiveAnalysisRead)
def create_analysis(payload: ExecutiveAnalysisCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExecutiveAnalysisRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return ai_service.create_analysis(db, payload, current_user.id)
