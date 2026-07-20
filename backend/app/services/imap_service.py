"""Sondeo de bandeja externa via IMAP (docs/96 item #11).

Bandeja de solo lectura: un perfil IMAP por proyecto, una sola carpeta
(INBOX), sondeo periodico desde el worker CLI existente
(`run_scheduled_tasks.py`), nunca en linea con una peticion HTTP -- una
conexion IMAP puede tardar segundos. `poll_profile` devuelve exactamente
la forma `(status, result_text)` que `scheduler_service._execute()` ya
espera del branch "backup".
"""

import logging
import re

from imap_tools import AND, MailBox
from imap_tools.message import MailMessage
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import to_naive_utc
from app.models.messages import ExternalMailMessage, MailProfile
from app.services.message_service import decrypt_mail_config

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(html: str) -> str:
    return _HTML_TAG_RE.sub(" ", html).strip()


def _build_row(profile: MailProfile, msg: MailMessage) -> ExternalMailMessage:
    body = msg.text or (strip_html(msg.html) if msg.html else "") or ""
    received_at = to_naive_utc(msg.date)
    return ExternalMailMessage(
        project_id=profile.project_id,
        mail_profile_id=profile.id,
        uid=int(msg.uid),
        from_address=msg.from_ or "",
        subject=msg.subject or "",
        body=body,
        received_at=received_at,
        status="unread",
    )


def poll_profile(db: Session, profile: MailProfile) -> tuple[str, str]:
    if profile.provider != "imap":
        return "failed", f"El perfil '{profile.name}' no es de tipo IMAP"
    if not profile.server_host or not profile.server_port:
        return "failed", "El perfil no tiene servidor IMAP configurado"

    credentials = decrypt_mail_config(profile.config_json)
    username = str(credentials.get("username") or profile.sender_email)
    password = credentials.get("password")
    if not password:
        return "failed", "El perfil no tiene contrasena IMAP configurada"

    highest_uid = profile.last_imap_uid or 0
    fetched = 0
    skipped = 0
    try:
        with MailBox(profile.server_host, port=int(profile.server_port)).login(
            username, str(password), initial_folder="INBOX"
        ) as mailbox:
            criteria = AND(uid=f"{highest_uid + 1}:*") if highest_uid else "ALL"
            for msg in mailbox.fetch(criteria, mark_seen=False):
                try:
                    row = _build_row(profile, msg)
                except Exception as exc:
                    skipped += 1
                    logger.warning("No fue posible interpretar un mensaje IMAP del perfil %s: %s", profile.id, exc)
                    continue
                if row.uid <= highest_uid:
                    continue
                db.add(row)
                profile.last_imap_uid = row.uid
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    skipped += 1
                    continue
                highest_uid = row.uid
                fetched += 1
    except Exception as exc:
        db.rollback()
        return "failed", f"No fue posible sondear el buzon IMAP: {exc}"[:500]

    return "success", f"{fetched} mensaje(s) nuevo(s), {skipped} omitido(s)"
