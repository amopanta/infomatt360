from datetime import datetime

from pydantic import BaseModel


class ParticipantCreate(BaseModel):
    project_id: str
    external_code: str | None = None
    document_id: str | None = None
    full_name: str
    participant_type: str = "person"
    status: str = "active"
    metadata_json: str | None = None


class ParticipantRead(ParticipantCreate):
    id: str
    duplicate_flag: str = "none"


class ParticipantHistoryItem(BaseModel):
    """Una captura del historial unificado del participante (ver docs/98).

    Agrupa formularios de cualquier plantilla/canal que quedaron enlazados a
    este participante, para verlos como un solo eje sin tener que revisar
    formulario por formulario.
    """

    record_id: str
    template_id: str
    template_name: str
    status: str
    created_at: datetime
    updated_at: datetime
    submitted_by: str | None = None
