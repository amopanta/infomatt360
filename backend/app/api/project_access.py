from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services.assignment_service import assignment_service


def require_project_access(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    has_access = assignment_service.user_has_project_access(db, current_user.id, project_id)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return current_user
