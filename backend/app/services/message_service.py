from sqlalchemy.orm import Session

from app.models.assignment import UserProjectAssignment
from app.models.identity import User
from app.models.messages import InternalMessage, MailProfile
from app.schemas.messages import InternalMessageCreate, InternalMessageRead, MailProfileCreate, MailProfileRead, MessageCounts


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
        created_at=row.created_at,
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

    def list_inbox(self, db: Session, project_id: str, recipient_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> list[InternalMessageRead]:
        query = db.query(InternalMessage).filter(
            InternalMessage.project_id == project_id,
            InternalMessage.recipient_id == recipient_id,
        )
        if status:
            query = query.filter(InternalMessage.status == status)
        rows = query.order_by(InternalMessage.created_at.desc()).offset(offset).limit(limit).all()
        return [msg_to_read(row) for row in rows]

    def list_sent(self, db: Session, project_id: str, sender_id: str, limit: int = 50, offset: int = 0) -> list[InternalMessageRead]:
        rows = db.query(InternalMessage).filter(
            InternalMessage.project_id == project_id,
            InternalMessage.sender_id == sender_id,
        ).order_by(InternalMessage.created_at.desc()).offset(offset).limit(limit).all()
        return [msg_to_read(row) for row in rows]

    def get_project_message_for_user(self, db: Session, message_id: str, project_id: str, user_id: str) -> InternalMessage | None:
        return db.query(InternalMessage).filter(
            InternalMessage.id == message_id,
            InternalMessage.project_id == project_id,
            InternalMessage.recipient_id == user_id,
        ).first()

    def set_status(self, db: Session, message: InternalMessage, status: str) -> InternalMessageRead:
        message.status = status
        db.add(message)
        db.commit()
        db.refresh(message)
        return msg_to_read(message)

    def counts(self, db: Session, project_id: str, user_id: str) -> MessageCounts:
        inbox = db.query(InternalMessage).filter(
            InternalMessage.project_id == project_id,
            InternalMessage.recipient_id == user_id,
        ).count()
        unread = db.query(InternalMessage).filter(
            InternalMessage.project_id == project_id,
            InternalMessage.recipient_id == user_id,
            InternalMessage.status == "unread",
        ).count()
        sent = db.query(InternalMessage).filter(
            InternalMessage.project_id == project_id,
            InternalMessage.sender_id == user_id,
        ).count()
        return MessageCounts(unread=unread, inbox=inbox, sent=sent)

    def user_exists_in_project(self, db: Session, user_id: str, project_id: str) -> bool:
        return db.query(UserProjectAssignment).join(User, User.id == UserProjectAssignment.user_id).filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.project_id == project_id,
            UserProjectAssignment.status == "active",
            User.status == "active",
        ).first() is not None


message_service = MessageService()
