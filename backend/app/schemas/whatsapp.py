from datetime import datetime

from pydantic import BaseModel


class WhatsAppNotificationRead(BaseModel):
    id: str
    project_id: str
    recipient_user_id: str | None = None
    recipient_phone: str
    message: str
    reference_record_id: str | None = None
    status: str
    error: str | None = None
    created_at: datetime
