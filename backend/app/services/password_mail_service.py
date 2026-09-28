import logging
from email.message import EmailMessage
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assignment import UserProjectAssignment
from app.models.identity import User
from app.models.messages import MailProfile
from app.services.mail_autoconfig_service import send_smtp_message
from app.services.message_service import decrypt_mail_config

logger = logging.getLogger(__name__)


class PasswordMailService:
    def send_reset_link(self, recipient: str, token: str, db: Session | None = None) -> bool:
        profile = self._profile_for_recipient(db, recipient) if db is not None else None
        sender = profile.sender_email if profile else settings.smtp_from_email
        host = profile.server_host if profile else settings.smtp_host
        port = profile.server_port if profile else settings.smtp_port
        credentials = decrypt_mail_config(profile.config_json) if profile else {
            "username": settings.smtp_username,
            "password": settings.smtp_password,
            "security": "ssl" if settings.smtp_port == 465 else ("starttls" if settings.smtp_use_tls else "none"),
        }
        if not host or not port or not sender:
            logger.warning("Recuperacion solicitada, pero SMTP no esta configurado")
            return False

        reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?{urlencode({'token': token})}"
        message = EmailMessage()
        message["Subject"] = "Restablecer contrasena de InfoMatt360"
        message["From"] = sender
        message["To"] = recipient
        message.set_content(
            "Recibimos una solicitud para restablecer tu contrasena de InfoMatt360.\n\n"
            f"Abre este enlace dentro de los proximos 30 minutos:\n{reset_url}\n\n"
            "Si no hiciste la solicitud, ignora este mensaje."
        )

        try:
            send_smtp_message(host, int(port), credentials, message)
            return True
        except Exception:
            logger.exception("No fue posible entregar el correo de recuperacion")
            return False

    def _profile_for_recipient(self, db: Session, recipient: str) -> MailProfile | None:
        user = db.query(User).filter(User.email == recipient.strip().lower(), User.status == "active").first()
        if user is None:
            return None
        project_ids = [row.project_id for row in db.query(UserProjectAssignment).filter(
            UserProjectAssignment.user_id == user.id,
            UserProjectAssignment.status == "active",
        ).all()]
        if not project_ids:
            return None
        return db.query(MailProfile).filter(
            MailProfile.project_id.in_(project_ids),
            MailProfile.provider == "smtp",
            MailProfile.status == "active",
            MailProfile.is_default == "true",
        ).order_by(MailProfile.created_at.desc()).first()


password_mail_service = PasswordMailService()
