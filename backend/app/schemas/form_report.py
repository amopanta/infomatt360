from datetime import datetime

from pydantic import BaseModel


class FormReportChoice(BaseModel):
    label: str
    count: int


class FormReportQuestion(BaseModel):
    name: str
    label: str
    field_type: str
    answered: int
    missing: int
    choices: list[FormReportChoice]
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_average: float | None = None


class FormReportMonth(BaseModel):
    month: str
    count: int


class FormReportRead(BaseModel):
    template_id: str
    template_name: str
    description: str | None
    status: str
    records_total: int
    records_by_status: dict[str, int]
    last_record_at: datetime | None
    months: list[FormReportMonth]
    questions: list[FormReportQuestion]
