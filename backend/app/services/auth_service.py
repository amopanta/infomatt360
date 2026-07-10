import hashlib
import json
import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_mfa_challenge_token, hash_password, verify_password
from app.core.time import utc_now
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.identity import PasswordResetToken, Project, RefreshToken, Role, User
from app.schemas.auth import LoginRequest, LoginResponse, MfaConfirmResponse, MfaDisableRequest, MfaSetupRequest, MfaSetupResponse, MfaStatusResponse, PasswordChangeRequest, PasswordResetRequest, RefreshRequest, SessionProject, SessionResponse, TokenResponse
from app.services.identity_service import identity_service
from app.services.mfa_service import mfa_service


class AuthService:
    def login(self, db: Session, payload: LoginRequest) -> LoginResponse:
        user = identity_service.get_user_by_email(db, str(payload.email))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no activo")
        if user.mfa_enabled:
            return LoginResponse(
                mfa_required=True,
                mfa_challenge_token=create_mfa_challenge_token(user.id, user.auth_version),
            )
        raw_refresh, family_id = self._create_refresh_token(db, user)
        db.commit()
        return LoginResponse(
            access_token=create_access_token(user.id, user.auth_version, family_id),
            refresh_token=raw_refresh,
        )

    def complete_mfa_login(self, db: Session, user: User, code: str) -> TokenResponse:
        valid = mfa_service.verify_totp(user, code) or mfa_service.consume_recovery_code(user, code)
        if not user.mfa_enabled or not valid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo MFA invalido")
        raw_refresh, family_id = self._create_refresh_token(db, user)
        db.add(AuditLog(user_id=user.id, module="identity", action="mfa_login", entity_type="user", entity_id=user.id))
        db.commit()
        return TokenResponse(
            access_token=create_access_token(user.id, user.auth_version, family_id),
            refresh_token=raw_refresh,
        )

    def setup_mfa(self, db: Session, user: User, payload: MfaSetupRequest) -> MfaSetupResponse:
        if user.mfa_enabled:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA ya esta activo")
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contrasena actual incorrecta")
        secret = mfa_service.new_secret()
        user.mfa_secret_encrypted = mfa_service.encrypt_secret(secret)
        user.mfa_enabled = False
        user.mfa_recovery_hashes = None
        user.mfa_last_counter = None
        db.commit()
        return MfaSetupResponse(secret=secret, provisioning_uri=mfa_service.provisioning_uri(user.email, secret))

    def confirm_mfa(self, db: Session, user: User, code: str) -> MfaConfirmResponse:
        if user.mfa_enabled or not user.mfa_secret_encrypted:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No hay una activacion MFA pendiente")
        if not mfa_service.verify_totp(user, code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codigo MFA invalido")
        recovery_codes, recovery_hashes = mfa_service.generate_recovery_codes()
        user.mfa_enabled = True
        user.mfa_recovery_hashes = recovery_hashes
        user.auth_version += 1
        self._revoke_user_refresh_tokens(db, user.id)
        db.add(AuditLog(user_id=user.id, module="identity", action="mfa_enabled", entity_type="user", entity_id=user.id))
        db.commit()
        return MfaConfirmResponse(message="MFA activado. Guarda los codigos de recuperacion.", recovery_codes=recovery_codes)

    def disable_mfa(self, db: Session, user: User, payload: MfaDisableRequest) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contrasena actual incorrecta")
        if not (mfa_service.verify_totp(user, payload.code) or mfa_service.consume_recovery_code(user, payload.code)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codigo MFA invalido")
        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        user.mfa_recovery_hashes = None
        user.mfa_last_counter = None
        user.auth_version += 1
        self._revoke_user_refresh_tokens(db, user.id)
        db.add(AuditLog(user_id=user.id, module="identity", action="mfa_disabled", entity_type="user", entity_id=user.id))
        db.commit()

    def mfa_status(self, user: User) -> MfaStatusResponse:
        return MfaStatusResponse(
            enabled=user.mfa_enabled,
            recovery_codes_remaining=len(json.loads(user.mfa_recovery_hashes or "[]")),
        )

    def refresh(self, db: Session, payload: RefreshRequest) -> TokenResponse:
        if not payload.refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")
        token_hash = hashlib.sha256(payload.refresh_token.encode("utf-8")).hexdigest()
        token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if token is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")
        user = db.query(User).filter(User.id == token.user_id, User.status == "active").first()
        now = utc_now()
        if token.revoked_at is not None:
            if user and token.auth_version == user.auth_version:
                user.auth_version += 1
                self._revoke_user_refresh_tokens(db, user.id, now)
                db.add(AuditLog(user_id=user.id, module="identity", action="refresh_token_reuse_detected", entity_type="user", entity_id=user.id))
                db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reutilizado")
        if user is None or token.expires_at <= now or token.auth_version != user.auth_version:
            token.revoked_at = now
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido o vencido")

        token.revoked_at = now
        raw_refresh, family_id, replacement = self._create_refresh_token(db, user, token.family_id, include_row=True)
        token.replaced_by_id = replacement.id
        db.commit()
        return TokenResponse(
            access_token=create_access_token(user.id, user.auth_version, family_id),
            refresh_token=raw_refresh,
        )

    def get_session(self, db: Session, user: User) -> SessionResponse:
        rows = (
            db.query(UserProjectAssignment, Project, Role)
            .join(Project, Project.id == UserProjectAssignment.project_id)
            .join(Role, Role.id == UserProjectAssignment.role_id)
            .filter(
                UserProjectAssignment.user_id == user.id,
                UserProjectAssignment.status == "active",
                Project.status == "active",
            )
            .order_by(Project.name.asc())
            .all()
        )
        return SessionResponse(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            must_change_password=user.must_change_password,
            projects=[
                SessionProject(
                    id=project.id,
                    name=project.name,
                    role_id=assignment.role_id,
                    permissions=[item.strip() for item in role.permissions.split(",") if item.strip()],
                )
                for assignment, project, role in rows
            ],
        )

    def change_password(self, db: Session, user: User, payload: PasswordChangeRequest) -> None:
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contraseña actual incorrecta")
        user.password_hash = hash_password(payload.new_password)
        user.must_change_password = False
        user.auth_version += 1
        self._revoke_user_refresh_tokens(db, user.id)
        db.add(AuditLog(
            user_id=user.id,
            module="identity",
            action="self_password_change",
            entity_type="user",
            entity_id=user.id,
        ))
        db.commit()

    def logout(self, db: Session, user: User) -> None:
        user.auth_version += 1
        self._revoke_user_refresh_tokens(db, user.id)
        db.add(AuditLog(
            user_id=user.id,
            module="identity",
            action="logout_all_sessions",
            entity_type="user",
            entity_id=user.id,
        ))
        db.commit()

    def issue_reset_token(self, db: Session, email: str) -> str | None:
        user = identity_service.get_user_by_email(db, email)
        # Ejecutar trabajo criptografico aun cuando no exista para reducir diferencias obvias.
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        if user is None or user.status != "active":
            hashlib.sha256(token_hash.encode("utf-8")).hexdigest()
            return None
        now = utc_now()
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).update({"used_at": now})
        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=now + timedelta(minutes=30)))
        db.commit()
        return raw_token

    def reset_password(self, db: Session, payload: PasswordResetRequest) -> None:
        token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
        now = utc_now()
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        ).first()
        if token is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o vencido")
        user = db.query(User).filter(User.id == token.user_id, User.status == "active").first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o vencido")
        user.password_hash = hash_password(payload.new_password)
        user.must_change_password = False
        user.auth_version += 1
        self._revoke_user_refresh_tokens(db, user.id, now)
        token.used_at = now
        db.add(AuditLog(
            user_id=user.id,
            module="identity",
            action="password_recovery_complete",
            entity_type="user",
            entity_id=user.id,
        ))
        db.commit()

    def _create_refresh_token(
        self,
        db: Session,
        user: User,
        family_id: str | None = None,
        *,
        include_row: bool = False,
    ):
        raw_token = secrets.token_urlsafe(48)
        row = RefreshToken(
            id=str(uuid4()),
            user_id=user.id,
            family_id=family_id or str(uuid4()),
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            auth_version=user.auth_version,
            expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
        )
        db.add(row)
        if include_row:
            return raw_token, row.family_id, row
        return raw_token, row.family_id

    def _revoke_user_refresh_tokens(self, db: Session, user_id: str, now=None) -> None:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now or utc_now()})


auth_service = AuthService()
