from pydantic import BaseModel


class MailProfileCreate(BaseModel):
    project_id: str
    name: str
    provider: str = "smtp"
    sender_email: str
    server_host: str | None = None
    server_port: str | None = None
    config_json: str | None = None
    is_default: bool = False
    status: str = "active"


class MailProfileRead(MailProfileCreate):
    id: str


class InternalMessageCreate(BaseModel):
    project_id: str
    recipient_id: str
    subject: str
    body: str


class InternalMessageRead(InternalMessageCreate):
    id: str
    sender_id: str | None = None
    status: str = "unread"
