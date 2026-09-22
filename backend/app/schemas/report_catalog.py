from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from app.core.time import to_naive_utc


class IndicatorDefinition(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    source_mode: Literal["automatic", "manual"] = "automatic"
    template_id: str | None = None
    value_field: str | None = None
    aggregation: Literal["count", "sum", "average", "unique_count"] = "count"
    goal: float = Field(ge=0)
    manual_actual: float | None = Field(default=None, ge=0)
    unit: str = Field(default="", max_length=30)
    municipality_field: str | None = None
    view_kind: Literal["progress", "table", "bar"] = "progress"

    @model_validator(mode="after")
    def check_source(self):
        if self.source_mode == "manual":
            if self.manual_actual is None:
                raise ValueError("Indica el avance actual del indicador manual")
            return self
        if not self.template_id:
            raise ValueError("Selecciona el formulario del indicador automático")
        if self.aggregation != "count" and not self.value_field:
            raise ValueError("Selecciona una variable para esta agregación")
        return self


class CommitteeActivity(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    progress: float = Field(ge=0, le=100)


class CommitteeAlert(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=1000)
    priority: Literal["high", "medium", "low"] = "medium"
    owner: str = Field(default="", max_length=120)
    next_action: str = Field(default="", max_length=500)


class CommitteeBudget(BaseModel):
    component: str = Field(min_length=1, max_length=180)
    planned: float = Field(ge=0)
    spent: float = Field(ge=0)


class CommitteeAgreement(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    owner: str = Field(default="", max_length=120)
    due_date: str = Field(default="", max_length=10)
    status: Literal["new", "pending", "in_progress", "done"] = "new"


class CommitteeDetails(BaseModel):
    meeting_at: datetime | None = None
    location: str = Field(default="", max_length=180)
    audience: str = Field(default="", max_length=180)
    activities: list[CommitteeActivity] = Field(default_factory=list, max_length=100)
    alerts: list[CommitteeAlert] = Field(default_factory=list, max_length=50)
    budget: list[CommitteeBudget] = Field(default_factory=list, max_length=50)
    previous_agreements: list[CommitteeAgreement] = Field(default_factory=list, max_length=100)
    new_agreements: list[CommitteeAgreement] = Field(default_factory=list, max_length=100)


class CatalogReportConfig(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=1000)
    report_kind: Literal["indicators", "committee"] = "indicators"
    committee: CommitteeDetails = Field(default_factory=CommitteeDetails)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    indicators: list[IndicatorDefinition] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def check_dates(self):
        if self.starts_at and self.ends_at and to_naive_utc(self.starts_at) > to_naive_utc(self.ends_at):
            raise ValueError("La fecha inicial debe ser anterior a la final")
        return self


class CatalogReportRead(CatalogReportConfig):
    id: str
    created_at: datetime


class MunicipalityMetric(BaseModel):
    municipality: str
    value: float


class IndicatorResult(BaseModel):
    title: str
    actual: float
    goal: float
    progress_percent: float | None
    unit: str
    municipalities: list[MunicipalityMetric]
    view_kind: Literal["progress", "table", "bar"] = "progress"


class CatalogReportResult(BaseModel):
    id: str
    name: str
    description: str
    report_kind: Literal["indicators", "committee"] = "indicators"
    committee: CommitteeDetails = Field(default_factory=CommitteeDetails)
    generated_at: datetime
    indicators: list[IndicatorResult]


class ReportShareRequest(BaseModel):
    expires_at: datetime | None = None


class ReportShareIssued(BaseModel):
    id: str
    token: str
    expires_at: datetime


class ReportShareRead(BaseModel):
    id: str
    expires_at: datetime | None
    status: str
