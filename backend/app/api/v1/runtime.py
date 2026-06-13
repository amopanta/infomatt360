"""
Proyecto: InfoMatt360
Modulo: Runtime API
Responsabilidad: Exponer endpoints para renderizar, guardar y consultar formularios Runtime.
Dependencias: FastAPI, servicios Runtime y RuntimeRecord.
Notas: Este modulo cierra el flujo MVP Builder -> Runtime -> Guardar -> Consultar.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.runtime import RuntimeTemplate
from app.schemas.runtime_record import RuntimeRecordCreate, RuntimeRecordRead
from app.services.runtime_record_service import runtime_record_service
from app.services.runtime_service import runtime_service

router = APIRouter()


@router.get("/template/{template_id}", response_model=RuntimeTemplate)
def get_template_runtime(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeTemplate:
    """Entrega el JSON runtime de una plantilla del Builder.

    Este endpoint permite que el frontend renderice un formulario sin conocer
    las tablas internas del constructor.
    """
    return runtime_service.build_template_runtime(db, template_id)


@router.post("/save", response_model=RuntimeRecordRead)
def save_runtime_record(payload: RuntimeRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeRecordRead:
    """Guarda una respuesta capturada desde el formulario Runtime."""
    return runtime_record_service.save_record(db, payload, current_user.id)


@router.get("/record/{record_id}", response_model=RuntimeRecordRead)
def get_runtime_record(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RuntimeRecordRead:
    """Consulta una respuesta Runtime por identificador."""
    record = runtime_record_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    return record


@router.get("/template/{template_id}/records", response_model=list[RuntimeRecordRead])
def list_runtime_records(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RuntimeRecordRead]:
    """Lista respuestas guardadas para una plantilla Runtime."""
    return runtime_record_service.list_template_records(db, template_id)
