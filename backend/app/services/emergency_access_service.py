"""Credenciales de emergencia con expiracion (time-boxed).

Cubre el caso de la especificacion original de "auditores de entes de
control externos o gestores con bloqueos de identidad en zonas rurales":
un administrador emite un codigo de un solo uso para una cuenta de usuario
existente, valido por un numero configurable de horas. Al canjearse, se
emite una sesion normal para ese usuario, pero con una expiracion recortada
al minimo entre la configuracion habitual del JWT y el tiempo restante de
la llave -- nunca dura mas que el "time-box" acordado. El codigo nunca se
guarda en texto plano (solo su hash SHA-256, igual que ManagerQrToken).
"""

import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.core.time import utc_now
from app.models.emergency_access import EmergencyAccessKey
from app.models.identity import User
from app.schemas.emergency_access import (
    EmergencyAccessKeyCreate,
    EmergencyAccessKeyIssued,
    EmergencyAccessKeyRead,
    EmergencyAccessRedeemResponse,
)
from app.services.assignment_service import assignment_service


def _hash_code(raw_code: str) -> str:
    return hashlib.sha256(raw_code.encode("utf-8")).hexdigest()


def _to_read(row: EmergencyAccessKey) -> EmergencyAccessKeyRead:
    return EmergencyAccessKeyRead(
        id=row.id,
        project_id=row.project_id,
        user_id=row.user_id,
        issued_by=row.issued_by,
        purpose=row.purpose,
        expires_at=row.expires_at,
        used_at=row.used_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


class EmergencyAccessService:
    def issue(self, db: Session, payload: EmergencyAccessKeyCreate, issued_by: str) -> EmergencyAccessKeyIssued:
        target_user = db.query(User).filter(User.id == payload.user_id).first()
        if target_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario indicado no existe")

        if not assignment_service.user_has_project_access(db, payload.user_id, payload.project_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El gestor no tiene acceso a ese proyecto")

        raw_code = secrets.token_hex(4).upper()
        row = EmergencyAccessKey(
            project_id=payload.project_id,
            user_id=payload.user_id,
            issued_by=issued_by,
            purpose=payload.purpose,
            code_hash=_hash_code(raw_code),
            expires_at=utc_now() + timedelta(hours=payload.hours_valid),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return EmergencyAccessKeyIssued(**_to_read(row).model_dump(), code=raw_code)

    def list_keys(self, db: Session, project_id: str) -> list[EmergencyAccessKeyRead]:
        rows = db.query(EmergencyAccessKey).filter(EmergencyAccessKey.project_id == project_id).order_by(EmergencyAccessKey.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def revoke(self, db: Session, key_id: str) -> EmergencyAccessKeyRead:
        row = db.query(EmergencyAccessKey).filter(EmergencyAccessKey.id == key_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Llave de emergencia no encontrada")
        if row.revoked_at is None:
            row.revoked_at = utc_now()
            db.commit()
            db.refresh(row)
        return _to_read(row)

    def redeem(self, db: Session, raw_code: str) -> EmergencyAccessRedeemResponse:
        row = db.query(EmergencyAccessKey).filter(EmergencyAccessKey.code_hash == _hash_code(raw_code)).first()
        now = utc_now()
        if row is None or row.used_at is not None or row.revoked_at is not None or row.expires_at <= now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codigo de emergencia invalido, vencido o ya utilizado")

        user = db.query(User).filter(User.id == row.user_id).first()
        if user is None or user.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cuenta asociada a este codigo ya no esta activa")

        row.used_at = now
        db.commit()

        remaining = row.expires_at - now
        session_length = min(remaining, timedelta(minutes=settings.access_token_expire_minutes))
        token_expires_at = now + session_length
        access_token = create_access_token(user.id, user.auth_version, expires_delta=session_length)
        return EmergencyAccessRedeemResponse(access_token=access_token, expires_at=token_expires_at)


emergency_access_service = EmergencyAccessService()
