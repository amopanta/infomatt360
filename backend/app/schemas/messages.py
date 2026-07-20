from datetime import datetime

from pydantic import BaseModel, Field


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


class MailProfileRead(BaseModel):
    id: str
    project_id: str
    name: str
    provider: str
    sender_email: str
    server_host: str | None = None
    server_port: str | None = None
    is_default: bool
    status: str
    last_imap_uid: int | None = None


class MailAutoconfigSuggestion(BaseModel):
    found: bool
    sender_email: str | None = None
    server_host: str | None = None
    server_port: str | None = None
    use_tls: bool | None = None


class MailTestSendResponse(BaseModel):
    sent: bool
    detail: str


class InternalMessageCreate(BaseModel):
    project_id: str
    recipient_id: str
    subject: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1)


class InternalMessageRead(InternalMessageCreate):
    id: str
    sender_id: str | None = None
    status: str = "unread"
    created_at: datetime | None = None


class InternalMessageUpdate(BaseModel):
    status: str = Field(pattern="^(unread|read|archived)$")


class MessageCounts(BaseModel):
    unread: int
    inbox: int
    sent: int


class ExternalMailMessageRead(BaseModel):
    id: str
    project_id: str
    mail_profile_id: str
    uid: int
    from_address: str
    subject: str
    body: str
    received_at: datetime | None = None
    fetched_at: datetime
    status: str = "unread"


class ExternalMailMessageUpdate(BaseModel):
    status: str = Field(pattern="^(unread|read|archived)$")
