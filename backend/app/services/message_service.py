from sqlalchemy.orm import Session

from app.models.messages import InternalMessage, MailProfile
from app.schemas.messages import InternalMessageCreate, InternalMessageRead, MailProfileCreate, MailProfileRead


def mail_to_read(row: MailProfile) -> MailProfileRead:
    return MailProfileRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        provider=row.provider,
        sender_email=row.sender_email,
        server_host=row.server_host,
        server_port=row.server_port,
        config_json=row.config_json,
        is_default=row.is_default == "true",
        status=row.status,
    )


def msg_to_read(row: InternalMessage) -> InternalMessageRead:
    return InternalMessageRead(
        id=row.id,
        project_id=row.project_id,
        recipient_id=row.recipient_id,
        subject=row.subject,
        body=row.body,
        sender_id=row.sender_id,
        status=row.status,
    )


class MessageService:
    def create_mail_profile(self, db: Session, payload: MailProfileCreate) -> MailProfileRead:
        row = MailProfile(
            project_id=payload.project_id,
            name=payload.name,
            provider=payload.provider,
            sender_email=payload.sender_email,
            server_host=payload.server_host,
            server_port=payload.server_port,
            config_json=payload.config_json,
            is_default="true" if payload.is_default else "false",
            status=payload.status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return mail_to_read(row)

    def list_mail_profiles(self, db: Session, project_id: str) -> list[MailProfileRead]:
        rows = db.query(MailProfile).filter(MailProfile.project_id == project_id).order_by(MailProfile.created_at.desc()).all()
        return [mail_to_read(row) for row in rows]

    def create_message(self, db: Session, payload: InternalMessageCreate, sender_id: str) -> InternalMessageRead:
        row = InternalMessage(**payload.model_dump(), sender_id=sender_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return msg_to_read(row)

    def list_messages(self, db: Session, project_id: str, recipient_id: str) -> list[InternalMessageRead]:
        rows = db.query(InternalMessage).filter(
            InternalMessage.project_id == project_id,
            InternalMessage.recipient_id == recipient_id,
        ).order_by(InternalMessage.created_at.desc()).all()
        return [msg_to_read(row) for row in rows]


message_service = MessageService()
