from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.review import ReviewActionCreate, ReviewActionRead
from app.services.assignment_service import assignment_service
from app.services.review_service import review_service

router = APIRouter()


@router.post("/actions", response_model=ReviewActionRead)
def apply_review_action(payload: ReviewActionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewActionRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return review_service.apply_action(db, payload, current_user.id)


@router.get("/records/{record_id}/actions", response_model=list[ReviewActionRead])
def list_review_actions(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ReviewActionRead]:
    return review_service.list_actions(db, record_id)
