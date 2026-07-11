from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.builder import BuilderTemplate
from app.models.reports import Report, ReportLink
from app.models.runtime_record import RuntimeRecord
from app.schemas.reports import ReportCreate, ReportLinkCreate, ReportLinkRead, ReportProjectSummary, ReportRead, ReportTemplateMetric


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
