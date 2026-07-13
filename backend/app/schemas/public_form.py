from pydantic import BaseModel, Field

from app.schemas.runtime_record import RuntimeValueCreate


class PublicFormSubmitRequest(BaseModel):
    """Envio anonimo de un formulario abierto. Sin `project_id`/`template_id`
    explicitos: ambos se resuelven del enlace publico validado por el token
    en la URL, para que un visitante no pueda enviar datos a un proyecto o
    plantilla distinta a la que el enlace realmente autoriza."""

    values: list[RuntimeValueCreate] = Field(default_factory=list)
    device_id: str | None = None


class PublicFormSubmitResponse(BaseModel):
    submitted: bool
    record_id: str
