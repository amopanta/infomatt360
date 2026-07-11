import json
import secrets
import string

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.time import utc_now
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.identity import RefreshToken, User
from app.schemas.security import AdminEmailUpdate, AdminMfaReset, AdminPasswordReset, AdminPasswordResetResponse, AdminUserRead


class AccountAdminService:
    def _target_user(self, db: Session, project_id: str, user_id: str) -> User:
        row = (
            db.query(User)
            .join(UserProjectAssignment, UserProjectAssignment.user_id == User.id)
            .filter(
                User.id == user_id,
                UserProjectAssignment.project_id == project_id,
                UserProjectAssignment.status == "active",
            )
            .first()
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no asignado al proyecto")
        return row

    def _reauthenticate(self, admin: User, password: str) -> None:
        if not verify_password(password, admin.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contraseña del administrador incorrecta")

    def list_users(self, db: Session, project_id: str) -> list[AdminUserRead]:
        rows = (
            db.query(User)
            .join(UserProjectAssignment, UserProjectAssignment.user_id == User.id)
            .filter(UserProjectAssignment.project_id == project_id, UserProjectAssignment.status == "active")
            .order_by(User.full_name.asc())
            .all()
        )
        return [AdminUserRead(id=row.id, full_name=row.full_name, email=row.email, status=row.status, must_change_password=row.must_change_password, mfa_enabled=row.mfa_enabled) for row in rows]

    def update_email(self, db: Session, project_id: str, user_id: str, payload: AdminEmailUpdate, admin: User) -> AdminUserRead:
        self._reauthenticate(admin, payload.admin_password)
        target = self._target_user(db, project_id, user_id)
        next_email = str(payload.email).strip().lower()
        duplicate = db.query(User).filter(func.lower(User.email) == next_email, User.id != target.id).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")
        previous_email = target.email
        target.email = next_email
        db.add(AuditLog(
            project_id=project_id,
            user_id=admin.id,
            module="identity",
            action="admin_email_update",
            entity_type="user",
            entity_id=target.id,
            before_json=json.dumps({"email": previous_email}),
            after_json=json.dumps({"email": next_email}),
        ))
        db.commit()
        return AdminUserRead(id=target.id, full_name=target.full_name, email=target.email, status=target.status, must_change_password=target.must_change_password, mfa_enabled=target.mfa_enabled)

    def reset_password(self, db: Session, project_id: str, user_id: str, payload: AdminPasswordReset, admin: User) -> AdminPasswordResetResponse:
        self._reauthenticate(admin, payload.admin_password)
        target = self._target_user(db, project_id, user_id)
        generated = payload.temporary_password is None
        temporary_password = payload.temporary_password or self._generate_temporary_password()
        target.password_hash = hash_password(temporary_password)
        target.must_change_password = True
        target.auth_version += 1
        db.query(RefreshToken).filter(
            RefreshToken.user_id == target.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": utc_now()})
        db.add(AuditLog(
            project_id=project_id,
            user_id=admin.id,
            module="identity",
            action="admin_password_reset",
            entity_type="user",
            entity_id=target.id,
            after_json=json.dumps({"must_change_password": True}),
        ))
        db.commit()
        return AdminPasswordResetResponse(
            message="Contraseña temporal creada. Debe cambiarse en el próximo ingreso.",
            temporary_password=temporary_password if generated else None,
        )

    def reset_mfa(self, db: Session, project_id: str, user_id: str, payload: AdminMfaReset, admin: User) -> None:
        self._reauthenticate(admin, payload.admin_password)
        target = self._target_user(db, project_id, user_id)
        target.mfa_enabled = False
        target.mfa_secret_encrypted = None
        target.mfa_recovery_hashes = None
        target.mfa_last_counter = None
        target.auth_version += 1
        db.query(RefreshToken).filter(
            RefreshToken.user_id == target.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": utc_now()})
        db.add(AuditLog(
            project_id=project_id,
            user_id=admin.id,
            module="identity",
            action="admin_mfa_reset",
            entity_type="user",
            entity_id=target.id,
            after_json=json.dumps({"mfa_enabled": False}),
        ))
        db.commit()

    def _generate_temporary_password(self) -> str:
        alphabet = string.ascii_letters + string.digits + "-_.!"
        return "".join(secrets.choice(alphabet) for _ in range(20))


account_admin_service = AccountAdminService()
