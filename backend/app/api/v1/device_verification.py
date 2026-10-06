"""Platform authenticator verification for form fields (WebAuthn).

The result proves user verification on a registered device, which can be a
fingerprint, face, or device PIN. It never represents a participant fingerprint.
"""

import base64
import json
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)
from webauthn.helpers.exceptions import WebAuthnException

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.config import settings
from app.core.permissions import RECORDS_WRITE
from app.core.time import utc_now
from app.db.session import get_db
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.device_verification import DeviceCredential, DeviceVerification
from app.models.identity import User
from app.services.assignment_service import assignment_service

router = APIRouter()


class BeginRequest(BaseModel):
    template_id: str
    component_id: str
    register_this_device: bool = False


class FinishRequest(BaseModel):
    verification_id: str
    credential: dict


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _relying_party() -> tuple[str, str]:
    origin = settings.frontend_url.rstrip("/")
    parsed = urlparse(origin)
    if not parsed.hostname or parsed.scheme not in {"https", "http"}:
        raise ValueError("Origen WebAuthn no configurado")
    return parsed.hostname, origin


def _require_field(db: Session, user: User, template_id: str, component_id: str) -> BuilderTemplate:
    template = db.get(BuilderTemplate, template_id)
    component = db.get(BuilderComponent, component_id)
    if template is None or component is None or component.template_id != template_id or component.component_type != "FINGERPRINT":
        raise HTTPException(status_code=404, detail="Campo de verificación no encontrado")
    if not assignment_service.user_has_project_access(db, user.id, template.project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    require_project_permission(db, user.id, template.project_id, RECORDS_WRITE)
    return template


@router.post("/begin")
def begin_verification(payload: BeginRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    _require_field(db, user, payload.template_id, payload.component_id)
    rp_id, _ = _relying_party()
    credentials = db.query(DeviceCredential).filter_by(user_id=user.id).all()
    challenge = secrets.token_bytes(32)
    if credentials and not payload.register_this_device:
        operation = "authenticate"
        options = generate_authentication_options(
            rp_id=rp_id,
            challenge=challenge,
            allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(row.credential_id)) for row in credentials],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
    else:
        operation = "register"
        options = generate_registration_options(
            rp_id=rp_id,
            rp_name="InfoMatt360",
            user_id=user.id.encode("utf-8"),
            user_name=user.email,
            challenge=challenge,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(row.credential_id)) for row in credentials],
        )
    event = DeviceVerification(
        user_id=user.id, template_id=payload.template_id, component_id=payload.component_id,
        challenge=_encode(challenge), operation=operation, expires_at=utc_now() + timedelta(minutes=5),
    )
    db.add(event)
    db.commit()
    return {"verification_id": event.id, "operation": operation, "public_key": json.loads(options_to_json(options))}


@router.post("/finish")
def finish_verification(payload: FinishRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    event = db.query(DeviceVerification).filter_by(id=payload.verification_id, user_id=user.id).with_for_update().first()
    if event is None or event.verified_at is not None or event.expires_at <= utc_now():
        raise HTTPException(status_code=422, detail="Solicitud de verificación vencida o ya utilizada")
    _require_field(db, user, event.template_id, event.component_id)
    rp_id, origin = _relying_party()
    try:
        if event.operation == "register":
            result = verify_registration_response(
                credential=payload.credential,
                expected_challenge=base64url_to_bytes(event.challenge),
                expected_rp_id=rp_id,
                expected_origin=origin,
                require_user_verification=True,
            )
            credential_id = _encode(result.credential_id)
            if db.query(DeviceCredential).filter_by(credential_id=credential_id).first():
                raise ValueError("Este dispositivo ya está registrado")
            db.add(DeviceCredential(
                user_id=user.id, credential_id=credential_id,
                public_key=_encode(result.credential_public_key), sign_count=result.sign_count,
            ))
            event.credential_id = credential_id
        elif event.operation == "authenticate":
            credential_id = str(payload.credential.get("id", ""))
            registered = db.query(DeviceCredential).filter_by(user_id=user.id, credential_id=credential_id).with_for_update().first()
            if registered is None:
                raise ValueError("Dispositivo no registrado para este usuario")
            result = verify_authentication_response(
                credential=payload.credential,
                expected_challenge=base64url_to_bytes(event.challenge),
                expected_rp_id=rp_id,
                expected_origin=origin,
                credential_public_key=base64url_to_bytes(registered.public_key),
                credential_current_sign_count=registered.sign_count,
                require_user_verification=True,
            )
            registered.sign_count = result.new_sign_count
            event.credential_id = credential_id
        else:
            raise ValueError("Operación de verificación inválida")
    except (WebAuthnException, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No se pudo validar el autenticador del dispositivo") from exc
    event.verified_at = utc_now()
    db.commit()
    return {"device_verification_id": event.id, "method": "device_user_verification", "verified_at": event.verified_at.isoformat() + "Z"}
