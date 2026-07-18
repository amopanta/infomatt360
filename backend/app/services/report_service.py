import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.reports import Report, ReportBoard, ReportLink
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.report_board import (
    ChartPoint,
    ChartWidget,
    CustomMetricByStatusChartSource,
    CustomMetricSource,
    KpiWidget,
    RecordsTotalSource,
    ReportBoardLayout,
    ReportBoardRead,
    ReportBoardUpdate,
    ReportWidget,
    ResolvedChart,
    ResolvedKpi,
    ResolvedTable,
    ResolvedWidget,
    StatusBreakdownChartSource,
    StatusCountSource,
    TableWidget,
    TemplateCountSource,
    TemplateTotalsChartSource,
)
from app.schemas.reports import ReportCreate, ReportLinkCreate, ReportLinkRead, ReportProjectSummary, ReportRead, ReportTemplateMetric

# Mismo catalogo que frontend/src/modules/builder/fieldCatalog.ts (categoria
# "Numericos" + "Experiencia") -- duplicado igual que ya se duplica el
# catalogo de tipos de campo entre frontend y backend.
NUMERIC_AGGREGATABLE_TYPES = {"NUMBER", "INTEGER", "DECIMAL", "PERCENTAGE", "CURRENCY", "RANGE", "NPS", "RATING", "LIKERT_5", "LIKERT_7"}

# Tablero por defecto para un proyecto sin configuracion guardada (docs/111).
# No es un port pixel a pixel de las 3 tarjetas viejas de ReportsApp.tsx --
# "Formularios con datos" no tiene una fuente equivalente limpia sin
# inventar una 5ta fuente de datos, asi que se simplifica honestamente.
DEFAULT_WIDGETS: list[ReportWidget] = [
    KpiWidget(title="Registros totales", source=RecordsTotalSource()),
    TableWidget(title="Resumen por formulario"),
    ChartWidget(title="Registros por estado", chart_kind="pie", source=StatusBreakdownChartSource()),
]


def report_to_read(row: Report) -> ReportRead:
    return ReportRead(id=row.id, project_id=row.project_id, name=row.name, report_type=row.report_type, query_json=row.query_json, layout_json=row.layout_json, status=row.status)


def link_to_read(row: ReportLink) -> ReportLinkRead:
    return ReportLinkRead(id=row.id, report_id=row.report_id, token=row.token, access_mode=row.access_mode, allow_download=row.allow_download == "true", status=row.status)


class ReportService:
    def create_report(self, db: Session, payload: ReportCreate) -> ReportRead:
        row = Report(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return report_to_read(row)

    def list_reports(self, db: Session, project_id: str) -> list[ReportRead]:
        rows = db.query(Report).filter(Report.project_id == project_id).order_by(Report.created_at.desc()).all()
        return [report_to_read(row) for row in rows]

    def create_link(self, db: Session, payload: ReportLinkCreate) -> ReportLinkRead:
        row = ReportLink(
            report_id=payload.report_id,
            token=payload.token,
            access_mode=payload.access_mode,
            allow_download="true" if payload.allow_download else "false",
            status=payload.status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return link_to_read(row)

    def project_summary(self, db: Session, project_id: str) -> ReportProjectSummary:
        templates = db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id).order_by(BuilderTemplate.name.asc()).all()
        status_rows = (
            db.query(RuntimeRecord.template_id, RuntimeRecord.status, func.count(RuntimeRecord.id))
            .filter(RuntimeRecord.project_id == project_id)
            .group_by(RuntimeRecord.template_id, RuntimeRecord.status)
            .all()
        )
        last_rows = (
            db.query(RuntimeRecord.template_id, func.max(RuntimeRecord.created_at))
            .filter(RuntimeRecord.project_id == project_id)
            .group_by(RuntimeRecord.template_id)
            .all()
        )
        by_template: dict[str, dict[str, int]] = {}
        for template_id, status, count in status_rows:
            by_template.setdefault(template_id, {})[status] = int(count)
        last_by_template = {template_id: last_record_at for template_id, last_record_at in last_rows}
        records_by_status: dict[str, int] = {}
        for statuses in by_template.values():
            for status, count in statuses.items():
                records_by_status[status] = records_by_status.get(status, 0) + count
        records_total = sum(records_by_status.values())
        metrics = [
            ReportTemplateMetric(
                template_id=template.id,
                template_name=template.name,
                template_status=template.status,
                records_total=sum(by_template.get(template.id, {}).values()),
                records_by_status=by_template.get(template.id, {}),
                percent_of_total=round((sum(by_template.get(template.id, {}).values()) / records_total) * 100, 2) if records_total else 0,
                last_record_at=last_by_template.get(template.id),
            )
            for template in templates
        ]
        metrics.sort(key=lambda item: (-item.records_total, item.template_name.lower()))
        return ReportProjectSummary(project_id=project_id, records_total=records_total, records_by_status=records_by_status, templates=metrics, generated_at=utc_now())

    # --- Constructor visual de tableros (docs/96 item #6, docs/111) ---

    def get_board_row(self, db: Session, project_id: str) -> ReportBoard | None:
        """Sin efecto secundario: si no hay fila guardada, no se inserta una
        -- el default vive en memoria (DEFAULT_WIDGETS), no en la base."""
        return db.query(ReportBoard).filter(ReportBoard.project_id == project_id).first()

    def update_board(self, db: Session, payload: ReportBoardUpdate) -> ReportBoard:
        for widget in payload.widgets:
            self._validate_widget(db, payload.project_id, widget)

        row = self.get_board_row(db, payload.project_id)
        widgets_json = ReportBoardLayout(widgets=payload.widgets).model_dump_json()
        if row is None:
            row = ReportBoard(project_id=payload.project_id, widgets_json=widgets_json)
            db.add(row)
        else:
            row.widgets_json = widgets_json
            row.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return row

    def _validate_widget(self, db: Session, project_id: str, widget: ReportWidget) -> None:
        sources = []
        if isinstance(widget, KpiWidget):
            sources.append(widget.source)
        elif isinstance(widget, ChartWidget):
            sources.append(widget.source)
        for source in sources:
            if isinstance(source, (CustomMetricSource, CustomMetricByStatusChartSource)):
                self._validate_custom_metric_source(db, project_id, source)

    def _validate_custom_metric_source(self, db: Session, project_id: str, source: CustomMetricSource | CustomMetricByStatusChartSource) -> None:
        template = db.query(BuilderTemplate).filter(BuilderTemplate.id == source.template_id, BuilderTemplate.project_id == project_id).first()
        if template is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La plantilla seleccionada no pertenece a este proyecto.")
        component = db.query(BuilderComponent).filter(BuilderComponent.template_id == source.template_id, BuilderComponent.name == source.field_name).first()
        if component is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El campo seleccionado no existe en el formulario.")
        if source.aggregation != "count" and component.component_type not in NUMERIC_AGGREGATABLE_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Este campo no admite la agregación seleccionada.")

    def resolve_board(self, db: Session, project_id: str, widgets: list[ReportWidget]) -> ReportBoardRead:
        summary = self.project_summary(db, project_id)
        resolved: list[ResolvedWidget] = [self._resolve_widget(db, summary, widget) for widget in widgets]
        return ReportBoardRead(project_id=project_id, widgets=widgets, summary=summary, resolved=resolved, generated_at=utc_now())

    def _resolve_widget(self, db: Session, summary: ReportProjectSummary, widget: ReportWidget) -> ResolvedWidget:
        if isinstance(widget, TableWidget):
            return ResolvedTable()
        if isinstance(widget, KpiWidget):
            value = self._resolve_kpi_value(db, summary, widget.source)
            display = f"{value:.2f}".rstrip("0").rstrip(".") if isinstance(value, float) and not value.is_integer() else str(int(value))
            return ResolvedKpi(value=value, display=display)
        points = self._resolve_chart_points(db, summary, widget.source)
        return ResolvedChart(points=points)

    def _resolve_kpi_value(self, db: Session, summary: ReportProjectSummary, source) -> float:
        if isinstance(source, RecordsTotalSource):
            return float(summary.records_total)
        if isinstance(source, StatusCountSource):
            return float(summary.records_by_status.get(source.status, 0))
        if isinstance(source, TemplateCountSource):
            return next((float(item.records_total) for item in summary.templates if item.template_id == source.template_id), 0.0)
        if isinstance(source, CustomMetricSource):
            return self._aggregate_custom_metric(db, source.template_id, source.field_name, source.aggregation)
        return 0.0

    def _resolve_chart_points(self, db: Session, summary: ReportProjectSummary, source) -> list[ChartPoint]:
        if isinstance(source, StatusBreakdownChartSource):
            return [ChartPoint(label=status_name, value=float(count)) for status_name, count in sorted(summary.records_by_status.items())]
        if isinstance(source, TemplateTotalsChartSource):
            return [ChartPoint(label=item.template_name, value=float(item.records_total)) for item in summary.templates]
        if isinstance(source, CustomMetricByStatusChartSource):
            by_status = self._aggregate_custom_metric_by_status(db, source.template_id, source.field_name, source.aggregation)
            return [ChartPoint(label=status_name, value=value) for status_name, value in sorted(by_status.items())]
        return []

    def _aggregate_custom_metric(self, db: Session, template_id: str, field_name: str, aggregation: str) -> float:
        values = self._numeric_values_for_field(db, template_id, field_name, aggregation)
        return self._apply_aggregation(values, aggregation)

    def _aggregate_custom_metric_by_status(self, db: Session, template_id: str, field_name: str, aggregation: str) -> dict[str, float]:
        rows = (
            db.query(RuntimeRecordValue.field_value_json, RuntimeRecord.status)
            .join(RuntimeRecord, RuntimeRecord.id == RuntimeRecordValue.record_id)
            .filter(RuntimeRecord.template_id == template_id, RuntimeRecordValue.field_name == field_name)
            .all()
        )
        buckets: dict[str, list[float]] = {}
        for raw_value, record_status in rows:
            decoded = self._decode_numeric_or_countable(raw_value, aggregation)
            if decoded is None:
                continue
            buckets.setdefault(record_status, []).append(decoded)
        return {status_name: self._apply_aggregation(values, aggregation) for status_name, values in buckets.items()}

    def _numeric_values_for_field(self, db: Session, template_id: str, field_name: str, aggregation: str) -> list[float]:
        rows = (
            db.query(RuntimeRecordValue.field_value_json)
            .join(RuntimeRecord, RuntimeRecord.id == RuntimeRecordValue.record_id)
            .filter(RuntimeRecord.template_id == template_id, RuntimeRecordValue.field_name == field_name)
            .all()
        )
        values = [self._decode_numeric_or_countable(row[0], aggregation) for row in rows]
        return [value for value in values if value is not None]

    def _decode_numeric_or_countable(self, raw_value: str, aggregation: str) -> float | None:
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed = raw_value
        if aggregation == "count":
            return 1.0 if parsed not in (None, "") else None
        if isinstance(parsed, (int, float)) and not isinstance(parsed, bool):
            return float(parsed)
        return None

    def _apply_aggregation(self, values: list[float], aggregation: str) -> float:
        if not values:
            return 0.0
        if aggregation == "count":
            return float(len(values))
        if aggregation == "sum":
            return sum(values)
        if aggregation == "average":
            return sum(values) / len(values)
        if aggregation == "min":
            return min(values)
        if aggregation == "max":
            return max(values)
        return 0.0

    def export_project_summary_xlsx(self, db: Session, project_id: str) -> bytes:
        summary = self.project_summary(db, project_id)
        status_rows = [["Estado", "Registros"], *[[status, count] for status, count in sorted(summary.records_by_status.items())]]
        template_rows = [
            ["Formulario", "Estado formulario", "Registros", "% del total", "Distribucion por estado", "Ultimo registro"],
            *[
                [
                    item.template_name,
                    item.template_status,
                    item.records_total,
                    item.percent_of_total,
                    ", ".join(f"{status}: {count}" for status, count in sorted(item.records_by_status.items())) or "Sin registros",
                    item.last_record_at.isoformat() if item.last_record_at else "",
                ]
                for item in summary.templates
            ],
        ]
        overview_rows = [
            ["Proyecto", summary.project_id],
            ["Registros totales", summary.records_total],
            ["Generado", summary.generated_at.isoformat()],
        ]
        return self._xlsx({
            "Resumen": overview_rows,
            "Estados": status_rows,
            "Formularios": template_rows,
        })

    def _xlsx(self, sheets: dict[str, list[list[object]]]) -> bytes:
        output = BytesIO()
        sheet_names = list(sheets)
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types(len(sheet_names)))
            archive.writestr("_rels/.rels", self._root_rels())
            archive.writestr("xl/workbook.xml", self._workbook(sheet_names))
            archive.writestr("xl/_rels/workbook.xml.rels", self._workbook_rels(len(sheet_names)))
            archive.writestr("xl/styles.xml", self._styles())
            for index, rows in enumerate(sheets.values(), start=1):
                archive.writestr(f"xl/worksheets/sheet{index}.xml", self._worksheet(rows))
        return output.getvalue()

    def _content_types(self, sheet_count: int) -> str:
        sheets = "".join(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for index in range(1, sheet_count + 1))
        return f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{sheets}</Types>'

    def _root_rels(self) -> str:
        return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'

    def _workbook(self, sheet_names: list[str]) -> str:
        sheets = "".join(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>' for index, name in enumerate(sheet_names, start=1))
        return f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'

    def _workbook_rels(self, sheet_count: int) -> str:
        sheets = "".join(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>' for index in range(1, sheet_count + 1))
        return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{sheets}<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'

    def _styles(self) -> str:
        return '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>'

    def _worksheet(self, rows: list[list[object]]) -> str:
        body = "".join(f'<row r="{row_index}">{"".join(self._cell(row_index, column_index, value) for column_index, value in enumerate(row, start=1))}</row>' for row_index, row in enumerate(rows, start=1))
        return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>'

    def _cell(self, row: int, column: int, value: object) -> str:
        ref = f"{self._column_name(column)}{row}"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{ref}"><v>{value}</v></c>'
        text = escape(self._safe_excel_text(str(value)))
        return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'

    def _column_name(self, index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    def _safe_excel_text(self, value: str) -> str:
        return f"'{value}" if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


report_service = ReportService()
