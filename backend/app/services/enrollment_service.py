import hashlib
import io
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.enrollment import ManagerQrToken
from app.schemas.enrollment import QrGenerateRequest, QrValidateRequest, QrValidateResponse


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class EnrollmentService:
    def generate_qr_png(self, db: Session, payload: QrGenerateRequest) -> tuple[bytes, str]:
        """Devuelve la imagen PNG y el token crudo.

        El token crudo tambien queda codificado dentro de la imagen QR (es lo
        que un dispositivo escanea), asi que exponerlo ademas en un header de
        la respuesta HTTP no expone informacion adicional.
        """
        raw_token = secrets.token_urlsafe(32)
        row = ManagerQrToken(
            project_id=payload.project_id,
            user_id=payload.user_id,
            token_hash=_hash_token(raw_token),
            expires_at=utc_now() + timedelta(minutes=payload.expires_in_minutes),
        )
        db.add(row)
        db.commit()

        enrollment_url = f"{settings.frontend_url}/enroll?token={raw_token}"
        import qrcode

        image = qrcode.make(enrollment_url)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), raw_token

    def validate(self, db: Session, payload: QrValidateRequest) -> QrValidateResponse:
        row = db.query(ManagerQrToken).filter(ManagerQrToken.token_hash == _hash_token(payload.token)).first()
        now = utc_now()
        if row is None or row.used_at is not None or row.expires_at <= now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo QR invalido o vencido")
        row.used_at = now
        if payload.device_fingerprint:
            row.device_fingerprint = payload.device_fingerprint
        db.commit()
        return QrValidateResponse(valid=True, project_id=row.project_id, user_id=row.user_id)


enrollment_service = EnrollmentService()
