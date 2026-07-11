"""Gateway de notificaciones WhatsApp via WAHA (https://waha.devlike.pro).

Inactivo por defecto: sin `WAHA_BASE_URL` configurado, `send_text()` no
intenta ninguna peticion de red y devuelve un `WhatsAppNotificationRead`
con `status="skipped"` -- el resto del flujo de revision no se entera ni se
interrumpe (mismo principio que `gdrive_storage_service.is_configured()`).

Usa `httpx` sincrono (no `httpx.AsyncClient`) para mantener el mismo estilo
que el resto de servicios HTTP salientes del backend (ver
`gdrive_storage_service.py`): los endpoints de FastAPI aqui son sincronos
(`def`, no `async def`), asi que un cliente async no aporta concurrencia
real y complicaria la firma de `review_service.apply_action`.
"""

import logging

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.whatsapp import WhatsAppNotification
from app.schemas.whatsapp import WhatsAppNotificationRead

logger = logging.getLogger(__name__)

SEND_TEXT_TIMEOUT_SECONDS = 15


def _to_read(row: WhatsAppNotification) -> WhatsAppNotificationRead:
    return WhatsAppNotificationRead(
        id=row.id, project_id=row.project_id, recipient_user_id=row.recipient_user_id,
        recipient_phone=row.recipient_phone, message=row.message,
        reference_record_id=row.reference_record_id, status=row.status,
        error=row.error, created_at=row.created_at,
    )


class WhatsAppService:
    def is_configured(self) -> bool:
        return bool(settings.waha_base_url)

    def send_text(
        self,
        db: Session,
        *,
        project_id: str,
        recipient_phone: str,
        message: str,
        recipient_user_id: str | None = None,
        reference_record_id: str | None = None,
    ) -> WhatsAppNotificationRead:
        """Envia un mensaje de texto y registra el intento en el ledger.

        No lanza si la peticion HTTP falla: el llamador (una notificacion
        de cambio de estado) no debe romperse porque el gateway de
        WhatsApp este caido. El resultado (`status`) le indica al llamador
        si el envio se completo, fallo, o se omitio por falta de config.
        """
        if not self.is_configured():
            row = WhatsAppNotification(
                project_id=project_id, recipient_user_id=recipient_user_id, recipient_phone=recipient_phone,
                message=message, reference_record_id=reference_record_id, status="skipped",
                error="WAHA_BASE_URL no esta configurado en este servidor",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _to_read(row)

        chat_id = self._to_chat_id(recipient_phone)
        try:
            response = httpx.post(
                f"{settings.waha_base_url.rstrip('/')}/api/sendText",
                json={"chatId": chat_id, "text": message, "session": settings.waha_session},
                headers={"X-Api-Key": settings.waha_api_key} if settings.waha_api_key else {},
                timeout=SEND_TEXT_TIMEOUT_SECONDS,
            )
            if response.status_code >= 400:
                status_value, error = "failed", f"HTTP {response.status_code}: {response.text[:500]}"
            else:
                status_value, error = "sent", None
        except httpx.HTTPError as exc:
            status_value, error = "failed", str(exc)[:500]
            logger.warning("Fallo al enviar WhatsApp via WAHA a %s: %s", recipient_phone, exc)

        row = WhatsAppNotification(
            project_id=project_id, recipient_user_id=recipient_user_id, recipient_phone=recipient_phone,
            message=message, reference_record_id=reference_record_id, status=status_value, error=error,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def list_notifications(self, db: Session, project_id: str) -> list[WhatsAppNotificationRead]:
        rows = db.query(WhatsAppNotification).filter(WhatsAppNotification.project_id == project_id).order_by(WhatsAppNotification.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def _to_chat_id(self, phone: str) -> str:
        """WAHA espera el numero en formato `<codigo><numero>@c.us`."""
        digits = "".join(character for character in phone if character.isdigit())
        return f"{digits}@c.us"


whatsapp_service = WhatsAppService()
