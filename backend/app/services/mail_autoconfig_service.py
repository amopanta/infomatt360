"""Sugerencia de configuracion SMTP por dominio y prueba de envio.

No implementa autodiscovery genuino (RFC 6186 / Thunderbird Autoconfig): esa
tecnica requiere resolver DNS/HTTPS por dominio y falla con frecuencia en
proveedores corporativos. En su lugar se usa una tabla de proveedores
conocidos, mas una prueba real de envio antes de guardar la cuenta.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.models.messages import MailProfile
from app.services.message_service import decrypt_mail_config

logger = logging.getLogger(__name__)

KNOWN_PROVIDERS: dict[str, dict[str, object]] = {
    "gmail.com": {"server_host": "smtp.gmail.com", "server_port": "587", "use_tls": True},
    "outlook.com": {"server_host": "smtp-mail.outlook.com", "server_port": "587", "use_tls": True},
    "hotmail.com": {"server_host": "smtp-mail.outlook.com", "server_port": "587", "use_tls": True},
    "live.com": {"server_host": "smtp-mail.outlook.com", "server_port": "587", "use_tls": True},
    "msn.com": {"server_host": "smtp-mail.outlook.com", "server_port": "587", "use_tls": True},
    "office365.com": {"server_host": "smtp.office365.com", "server_port": "587", "use_tls": True},
    "yahoo.com": {"server_host": "smtp.mail.yahoo.com", "server_port": "587", "use_tls": True},
    "zoho.com": {"server_host": "smtp.zoho.com", "server_port": "587", "use_tls": True},
}


class MailAutoconfigService:
    def suggest_config(self, email: str) -> dict[str, object] | None:
        domain = email.strip().lower().rsplit("@", maxsplit=1)[-1]
        suggestion = KNOWN_PROVIDERS.get(domain)
        if suggestion is None:
            return None
        return {"sender_email": email, **suggestion}

    def send_test_email(self, profile: MailProfile) -> tuple[bool, str]:
        if not profile.server_host or not profile.server_port:
            return False, "El perfil no tiene servidor SMTP configurado"

        credentials = decrypt_mail_config(profile.config_json)
        message = EmailMessage()
        message["Subject"] = "Prueba de configuracion de correo InfoMatt360"
        message["From"] = profile.sender_email
        message["To"] = profile.sender_email
        message.set_content("Este es un correo de prueba para validar la configuracion SMTP del perfil.")

        try:
            send_smtp_message(profile.server_host, int(profile.server_port), credentials, message)
            return True, "Correo de prueba enviado"
        except (OSError, ValueError, smtplib.SMTPException) as exc:
            logger.warning("Prueba de envio SMTP fallida para perfil %s: %s", profile.id, exc)
            return False, "No fue posible enviar el correo de prueba. Revisa servidor, puerto, seguridad y credenciales."


def send_smtp_message(host: str, port: int, credentials: dict[str, object], message: EmailMessage) -> None:
    """Envia por SMTP configurable, conservando perfiles STARTTLS anteriores."""
    security = credentials.get("security")
    if security is None:
        security = "starttls" if credentials.get("use_tls", True) else "none"
    if security not in {"starttls", "ssl", "none"}:
        raise ValueError("Modo de seguridad SMTP invalido")
    context = ssl.create_default_context()
    client = smtplib.SMTP_SSL(host, port, timeout=15, context=context) if security == "ssl" else smtplib.SMTP(host, port, timeout=15)
    with client as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        username = credentials.get("username")
        password = credentials.get("password")
        if username and password:
            smtp.login(str(username), str(password))
        smtp.send_message(message)


mail_autoconfig_service = MailAutoconfigService()
