from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.runtime import RuntimeTemplate
from app.services.runtime_service import runtime_service

router = APIRouter()


@router.get("/template/{template_id}", response_model=RuntimeTemplate)
def get_template_runtime(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeTemplate:
    """Entrega el JSON runtime de una plantilla del Builder.

    Este endpoint es el primer paso del Runtime MVP: permite que el frontend
    renderice un formulario sin conocer las tablas internas del constructor.
    """
    return runtime_service.build_template_runtime(db, template_id)
