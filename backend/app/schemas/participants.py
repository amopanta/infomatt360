from datetime import datetime

from pydantic import BaseModel, model_validator


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


class ParticipantPromoteRequest(BaseModel):
    """Promueve un registro de la base abierta a la base cerrada (ver docs/99).

    Un registro capturado sin participante enlazado (base abierta: no hay
    certeza previa de quien es la persona) se puede convertir explicitamente
    en un participante de la base cerrada -- enlazandolo a uno YA existente
    (`participant_id`, para corregir un enlace automatico que no encontro
    coincidencia por un error de digitacion) o creando uno nuevo
    (`full_name` + opcionalmente `document_id`/`external_code`). Es siempre
    una accion humana explicita, nunca automatica -- ver la logica de
    auto-enlace en `runtime_record_service._resolve_participant`, que a
    proposito nunca crea participantes por si sola.
    """

    record_id: str
    participant_id: str | None = None
    full_name: str | None = None
    document_id: str | None = None
    external_code: str | None = None
    participant_type: str = "person"

    @model_validator(mode="after")
    def require_target(self):
        if not self.participant_id and not self.full_name:
            raise ValueError("Indica participant_id (enlazar existente) o full_name (crear un participante nuevo)")
        return self
