"""Constructor visual de reportes/tableros (docs/96 item #6, docs/111).

Union discriminada de widgets, siguiendo el mismo patron que los bloques de
acta (`app.schemas.acta`, docs/109): se persiste como JSON (`widgets_json`)
y se resuelve enteramente del lado del servidor en un solo response
(`ReportBoardRead.resolved`, alineado por posicion con `widgets`).
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.reports import ReportProjectSummary

Aggregation = Literal["count", "sum", "average", "min", "max"]


# --- Fuentes de datos para widgets KPI ---


class RecordsTotalSource(BaseModel):
    kind: Literal["records_total"] = "records_total"


class StatusCountSource(BaseModel):
    kind: Literal["status_count"] = "status_count"
    status: str = Field(..., min_length=1)


class TemplateCountSource(BaseModel):
    kind: Literal["template_count"] = "template_count"
    template_id: str


class CustomMetricSource(BaseModel):
    kind: Literal["custom_metric"] = "custom_metric"
    template_id: str
    field_name: str
    aggregation: Aggregation


KpiSource = Annotated[
    RecordsTotalSource | StatusCountSource | TemplateCountSource | CustomMetricSource,
    Field(discriminator="kind"),
]


# --- Fuentes de datos para widgets de grafico (varias categorias, no un solo numero) ---


class StatusBreakdownChartSource(BaseModel):
    kind: Literal["status_breakdown"] = "status_breakdown"


class TemplateTotalsChartSource(BaseModel):
    kind: Literal["template_totals"] = "template_totals"


class CustomMetricByStatusChartSource(BaseModel):
    kind: Literal["custom_metric_by_status"] = "custom_metric_by_status"
    template_id: str
    field_name: str
    aggregation: Aggregation


ChartSource = Annotated[
    StatusBreakdownChartSource | TemplateTotalsChartSource | CustomMetricByStatusChartSource,
    Field(discriminator="kind"),
]


# --- Widgets ---


class KpiWidget(BaseModel):
    type: Literal["kpi"] = "kpi"
    title: str = Field(..., min_length=1)
    source: KpiSource = Field(default_factory=RecordsTotalSource)


class TableWidget(BaseModel):
    type: Literal["table"] = "table"
    title: str = Field(..., min_length=1)


class ChartWidget(BaseModel):
    type: Literal["chart"] = "chart"
    title: str = Field(..., min_length=1)
    chart_kind: Literal["bar", "pie"] = "bar"
    source: ChartSource = Field(default_factory=StatusBreakdownChartSource)


ReportWidget = Annotated[KpiWidget | TableWidget | ChartWidget, Field(discriminator="type")]


class ReportBoardLayout(BaseModel):
    widgets: list[ReportWidget] = Field(default_factory=list)


class ReportBoardUpdate(BaseModel):
    project_id: str
    widgets: list[ReportWidget]


# --- Valores resueltos, alineados por posicion con `widgets` ---


class ChartPoint(BaseModel):
    label: str
    value: float


class ResolvedKpi(BaseModel):
    kind: Literal["kpi"] = "kpi"
    value: float
    display: str


class ResolvedChart(BaseModel):
    kind: Literal["chart"] = "chart"
    points: list[ChartPoint]


class ResolvedTable(BaseModel):
    kind: Literal["table"] = "table"


ResolvedWidget = Annotated[ResolvedKpi | ResolvedChart | ResolvedTable, Field(discriminator="kind")]


class ReportBoardRead(BaseModel):
    project_id: str
    widgets: list[ReportWidget]
    summary: ReportProjectSummary
    resolved: list[ResolvedWidget]
    generated_at: datetime
