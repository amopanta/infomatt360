"""
Proyecto: InfoMatt360
Modulo: Runtime Record Schemas
Responsabilidad: Definir contratos API para guardar y consultar respuestas Runtime.
Dependencias: Pydantic.
Notas: field_value_json permite conservar valores simples y complejos sin alterar base de datos.
"""

from pydantic import BaseModel


class RuntimeValueCreate(BaseModel):
    """Valor capturado para un campo del formulario Runtime."""

    component_id: str | None = None
    field_name: str
    field_value_json: str


class RuntimeRecordCreate(BaseModel):
    """Solicitud para guardar una captura completa desde Runtime."""

    project_id: str
    template_id: str
    version_id: str | None = None
    status: str = "submitted"
    device_id: str | None = None
    ip_address: str | None = None
    values: list[RuntimeValueCreate]


class RuntimeValueRead(RuntimeValueCreate):
    id: str
    record_id: str


class RuntimeRecordRead(BaseModel):
    """Respuesta consolidada de una captura Runtime."""

    id: str
    project_id: str
    template_id: str
    version_id: str | None = None
    status: str
    submitted_by: str | None = None
    device_id: str | None = None
    ip_address: str | None = None
    values: list[RuntimeValueRead] = []
