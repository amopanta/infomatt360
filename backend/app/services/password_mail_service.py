import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)


class PasswordMailService:
    def send_reset_link(self, recipient: str, token: str) -> bool:
        if not settings.smtp_host or not settings.smtp_from_email:
            logger.warning("Recuperacion solicitada, pero SMTP no esta configurado")
            return False

        reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?{urlencode({'token': token})}"
        message = EmailMessage()
        message["Subject"] = "Restablecer contrasena de InfoMatt360"
        message["From"] = settings.smtp_from_email
        message["To"] = recipient
        message.set_content(
            "Recibimos una solicitud para restablecer tu contrasena de InfoMatt360.\n\n"
            f"Abre este enlace dentro de los proximos 30 minutos:\n{reset_url}\n\n"
            "Si no hiciste la solicitud, ignora este mensaje."
        )

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
            return True
        except (OSError, smtplib.SMTPException):
            logger.exception("No fue posible entregar el correo de recuperacion")
            return False


password_mail_service = PasswordMailService()
