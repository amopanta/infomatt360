"""CRUD de asignaciones de dispositivos a usuarios por proyecto."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.core.time import utc_now
from app.db.session import get_db
from app.models.device_assignment import UserDeviceAssignment
from app.models.identity import User
from app.schemas.device_assignment import DeviceAssignmentCreate, DeviceAssignmentRead, DeviceAssignmentUpdate
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.get("/{project_id}", response_model=list[DeviceAssignmentRead])
def list_device_assignments(
    project_id: str,
    user_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    query = db.query(UserDeviceAssignment).filter(UserDeviceAssignment.project_id == project_id)
    if user_id:
        query = query.filter(UserDeviceAssignment.user_id == user_id)
    if status:
        query = query.filter(UserDeviceAssignment.status == status)
    return query.order_by(UserDeviceAssignment.created_at.desc()).all()


@router.post("/{project_id}", response_model=DeviceAssignmentRead, status_code=201)
def register_device(
    project_id: str,
    payload: DeviceAssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    if not db.get(User, payload.user_id) or not assignment_service.user_has_project_access(db, payload.user_id, project_id):
        raise HTTPException(status_code=422, detail="El usuario debe tener acceso al proyecto")

    # Check for duplicate active assignment
    existing = (
        db.query(UserDeviceAssignment)
        .filter(
            UserDeviceAssignment.project_id == project_id,
            UserDeviceAssignment.user_id == payload.user_id,
            UserDeviceAssignment.device_fingerprint == payload.device_fingerprint,
            UserDeviceAssignment.status == "active",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Este dispositivo ya está registrado y activo para el usuario")

    row = UserDeviceAssignment(
        project_id=project_id,
        user_id=payload.user_id,
        device_fingerprint=payload.device_fingerprint.strip(),
        device_name=payload.device_name.strip(),
        device_os=payload.device_os.strip(),
        device_model=payload.device_model.strip(),
        app_version=payload.app_version.strip(),
        notes=payload.notes,
        registered_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{project_id}/{assignment_id}", response_model=DeviceAssignmentRead)
def update_device_assignment(
    project_id: str,
    assignment_id: str,
    payload: DeviceAssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    row = db.query(UserDeviceAssignment).filter(UserDeviceAssignment.id == assignment_id, UserDeviceAssignment.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Asignación de dispositivo no encontrada")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.updated_at = utc_now()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{project_id}/{assignment_id}", status_code=204)
def revoke_device(
    project_id: str,
    assignment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    row = db.query(UserDeviceAssignment).filter(UserDeviceAssignment.id == assignment_id, UserDeviceAssignment.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Asignación de dispositivo no encontrada")
    row.status = "revoked"
    row.updated_at = utc_now()
    db.commit()
