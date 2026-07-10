"""
Proyecto: InfoMatt360
Modulo: Runtime Record Schemas
Responsabilidad: Definir contratos API para guardar y consultar respuestas Runtime.
Dependencias: Pydantic.
Notas: field_value_json permite conservar valores simples y complejos sin alterar base de datos.
"""

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RuntimeValueCreate(BaseModel):
    """Valor capturado para un campo del formulario Runtime."""

    component_id: str | None = None
    field_name: str = Field(..., min_length=1)
    field_value_json: str

    @field_validator("field_value_json")
    @classmethod
    def validate_json_value(cls, value: str) -> str:
        try:
            json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("field_value_json debe contener JSON valido") from exc
        return value


class RuntimeRecordCreate(BaseModel):
    """Solicitud para guardar una captura completa desde Runtime."""

    project_id: str
    template_id: str
    version_id: str | None = None
    status: Literal["draft", "submitted", "approved", "rejected", "archived"] = "submitted"
    device_id: str | None = None
    ip_address: str | None = None
    values: list[RuntimeValueCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_fields(self):
        names = [item.field_name for item in self.values]
        if len(names) != len(set(names)):
            raise ValueError("No se permiten campos duplicados en un registro Runtime")
        return self


class RuntimeBulkSaveRequest(BaseModel):
    """Carga masiva de registros para integraciones externas."""

    project_id: str
    template_id: str
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)
    processing_mode: Literal["immediate", "queued"] = "immediate"
    records: list[RuntimeRecordCreate] = Field(default_factory=list, min_length=1, max_length=10000)
    continue_on_error: bool = True


class RuntimeBulkSaveItemResult(BaseModel):
    index: int
    id: str | None = None
    status: str
    error: str | None = None


class RuntimeBulkSaveResponse(BaseModel):
    project_id: str
    template_id: str
    job_id: str | None = None
    idempotency_key: str | None = None
    job_status: str = "completed"
    processing_mode: str = "immediate"
    replayed: bool = False
    received: int
    created: int
    failed: int
    results: list[RuntimeBulkSaveItemResult] = Field(default_factory=list)


class RuntimeBulkJobRead(BaseModel):
    id: str
    project_id: str
    template_id: str
    idempotency_key: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    worker_id: str | None = None
    locked_at: datetime | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    received: int = 0
    created: int = 0
    failed: int = 0
    replayable: bool = True


class RuntimeBulkJobDetail(RuntimeBulkJobRead):
    response: RuntimeBulkSaveResponse | None = None


class RuntimeBulkJobSummary(BaseModel):
    project_id: str
    total_jobs: int = 0
    queued_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_received: int = 0
    total_created: int = 0
    total_failed: int = 0
    success_rate: float = 0


class RuntimeValueRead(RuntimeValueCreate):
    id: str
    record_id: str


class RuntimeRecordRead(BaseModel):
    """Respuesta consolidada de una captura Runtime."""

    id: str
    project_id: str
    template_id: str
    version_id: str | None = None
    approval_flow_id: str | None = None
    approval_flow_version: str | None = None
    status: str
    submitted_by: str | None = None
    device_id: str | None = None
    ip_address: str | None = None
    duplicate_flag: str = "none"
    created_at: datetime
    updated_at: datetime
    values: list[RuntimeValueRead] = Field(default_factory=list)


class RuntimeRecordPage(BaseModel):
    """Respuesta paginada para consultas operativas de registros Runtime."""

    items: list[RuntimeRecordRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
