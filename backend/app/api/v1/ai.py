from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import allowed_participant_ids, participant_visible, require_record_id_territory
from app.db.session import get_db
from app.models.files import FileAsset
from app.models.identity import User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.ai import AiCheckCreate, AiCheckRead, ExecutiveAnalysisCreate, ExecutiveAnalysisRead, OcrResultCreate, OcrResultRead
from app.services.ai_service import ai_service
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.post("/checks", response_model=AiCheckRead)
def create_check(payload: AiCheckCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AiCheckRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    # H11: el registro y el archivo deben ser de este proyecto y del territorio del usuario.
    if payload.record_id:
        record = db.get(RuntimeRecord, payload.record_id)
        if record is None or record.project_id != payload.project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
        require_record_id_territory(db, current_user.id, payload.record_id)
    if payload.file_id:
        asset = db.get(FileAsset, payload.file_id)
        if asset is None or asset.project_id != payload.project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
        if asset.record_id:
            require_record_id_territory(db, current_user.id, asset.record_id)
        elif asset.participant_id and (participant := db.get(Participant, asset.participant_id)) and not participant_visible(db, current_user.id, participant):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
    return ai_service.create_check(db, payload, current_user.id)


@router.get("/checks/{project_id}", response_model=list[AiCheckRead])
def list_checks(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[AiCheckRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    checks = ai_service.list_checks(db, project_id)
    # H11: el resultado puede citar datos del registro; solo los del territorio.
    allowed = allowed_participant_ids(db, current_user.id, project_id)
    if allowed is None:
        return checks
    allowed_set = set(allowed)
    record_participant = {
        rid: pid for rid, pid in db.query(RuntimeRecord.id, RuntimeRecord.participant_id)
        .filter(RuntimeRecord.id.in_([c.record_id for c in checks if c.record_id])).all()
    }
    return [c for c in checks if not c.record_id or record_participant.get(c.record_id) in allowed_set]


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
