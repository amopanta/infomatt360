"""Named indicator reports backed by form responses; public views contain aggregates only."""

import hashlib
import json
import secrets
from collections import defaultdict
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.time import to_naive_utc, utc_now
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.reports import Report, ReportLink
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.report_catalog import (
    CatalogReportConfig,
    CatalogReportRead,
    CatalogReportResult,
    IndicatorDefinition,
    IndicatorResult,
    MunicipalityMetric,
    ReportShareIssued,
    ReportShareRead,
)
from app.services.report_service import NUMERIC_AGGREGATABLE_TYPES


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")


class ReportCatalogService:
    def get(self, db: Session, report_id: str) -> Report:
        row = db.query(Report).filter(Report.id == report_id, Report.report_type == "indicator_board").first()
        if row is None:
            raise _not_found()
        return row

    def config(self, row: Report) -> CatalogReportConfig:
        return CatalogReportConfig.model_validate_json(row.query_json)

    def read(self, row: Report) -> CatalogReportRead:
        return CatalogReportRead(id=row.id, created_at=row.created_at, **self.config(row).model_dump())

    def validate(self, db: Session, config: CatalogReportConfig) -> None:
        for item in config.indicators:
            if item.source_mode == "manual":
                continue
            template = db.query(BuilderTemplate).filter(BuilderTemplate.id == item.template_id, BuilderTemplate.project_id == config.project_id).first()
            if template is None:
                raise HTTPException(status_code=422, detail=f"El formulario de «{item.title}» no pertenece al proyecto")
            for field_name in {item.value_field, item.municipality_field} - {None, ""}:
                component = db.query(BuilderComponent).filter(BuilderComponent.template_id == item.template_id, BuilderComponent.name == field_name).first()
                if component is None:
                    raise HTTPException(status_code=422, detail=f"La variable «{field_name}» no existe en «{template.name}»")
                if field_name == item.value_field and item.aggregation in {"sum", "average"} and component.component_type not in NUMERIC_AGGREGATABLE_TYPES:
                    raise HTTPException(status_code=422, detail=f"«{field_name}» debe ser numérica para suma o promedio")

    def create(self, db: Session, config: CatalogReportConfig) -> CatalogReportRead:
        self.validate(db, config)
        row = Report(project_id=config.project_id, name=config.name, report_type="indicator_board", query_json=config.model_dump_json(), status="active")
        db.add(row)
        db.commit()
        db.refresh(row)
        return self.read(row)

    def update(self, db: Session, row: Report, config: CatalogReportConfig) -> CatalogReportRead:
        if config.project_id != row.project_id:
            raise HTTPException(status_code=422, detail="El proyecto del reporte no se puede cambiar")
        self.validate(db, config)
        row.name = config.name
        row.query_json = config.model_dump_json()
        db.commit()
        db.refresh(row)
        return self.read(row)

    @staticmethod
    def _decoded(raw: str | None):
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    @staticmethod
    def _has_value(value) -> bool:
        return value is not None and value != "" and value != []

    def _indicator(self, db: Session, config: CatalogReportConfig, item: IndicatorDefinition) -> IndicatorResult:
        if item.source_mode == "manual":
            actual = item.manual_actual or 0.0
            return IndicatorResult(title=item.title, actual=actual, goal=item.goal, progress_percent=round(actual / item.goal * 100, 1) if item.goal else None, unit=item.unit, municipalities=[], view_kind=item.view_kind)
        query = db.query(RuntimeRecord.id).filter(RuntimeRecord.project_id == config.project_id, RuntimeRecord.template_id == item.template_id, RuntimeRecord.status != "draft")
        if config.starts_at:
            query = query.filter(RuntimeRecord.created_at >= to_naive_utc(config.starts_at))
        if config.ends_at:
            query = query.filter(RuntimeRecord.created_at <= to_naive_utc(config.ends_at))
        record_ids = [record_id for (record_id,) in query.all()]
        wanted = {field for field in (item.value_field, item.municipality_field) if field}
        fields: dict[str, dict[str, object]] = defaultdict(dict)
        if wanted and record_ids:
            # Batch ids to stay below SQLite's parameter limit in tests and
            # keep the same behavior for large PostgreSQL projects.
            for offset in range(0, len(record_ids), 500):
                rows = db.query(RuntimeRecordValue.record_id, RuntimeRecordValue.field_name, RuntimeRecordValue.field_value_json).filter(RuntimeRecordValue.record_id.in_(record_ids[offset:offset + 500]), RuntimeRecordValue.field_name.in_(wanted)).order_by(RuntimeRecordValue.created_at, RuntimeRecordValue.id).all()
                for record_id, field_name, raw in rows:
                    fields[record_id][field_name] = self._decoded(raw)

        values: list[float] = []
        distinct: set[str] = set()
        municipality_values: dict[str, list[float]] = defaultdict(list)
        municipality_distinct: dict[str, set[str]] = defaultdict(set)
        for record_id in record_ids:
            value = fields[record_id].get(item.value_field) if item.value_field else None
            if item.aggregation == "count":
                if item.value_field and not self._has_value(value):
                    continue
                amount = 1.0
            elif item.aggregation == "unique_count":
                if not self._has_value(value):
                    continue
                amount = 1.0
                distinct.add(str(value))
            else:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                amount = float(value)
            values.append(amount)
            if item.municipality_field:
                municipality = fields[record_id].get(item.municipality_field)
                label = str(municipality).strip() if self._has_value(municipality) else "Sin municipio"
                municipality_values[label].append(amount)
                if item.aggregation == "unique_count":
                    municipality_distinct[label].add(str(value))

        if item.aggregation == "unique_count":
            actual = float(len(distinct))
        elif item.aggregation == "average":
            actual = sum(values) / len(values) if values else 0.0
        else:
            actual = sum(values)
        municipalities = []
        for label, amounts in municipality_values.items():
            if item.aggregation == "unique_count":
                amount = float(len(municipality_distinct[label]))
            elif item.aggregation == "average":
                amount = sum(amounts) / len(amounts)
            else:
                amount = sum(amounts)
            municipalities.append(MunicipalityMetric(municipality=label, value=round(amount, 2)))
        municipalities.sort(key=lambda row: (-row.value, row.municipality))
        return IndicatorResult(title=item.title, actual=round(actual, 2), goal=item.goal, progress_percent=round(actual / item.goal * 100, 1) if item.goal else None, unit=item.unit, municipalities=municipalities, view_kind=item.view_kind)

    def resolve(self, db: Session, row: Report) -> CatalogReportResult:
        config = self.config(row)
        return CatalogReportResult(id=row.id, name=config.name, description=config.description, generated_at=utc_now(), indicators=[self._indicator(db, config, item) for item in config.indicators])

    def issue_link(self, db: Session, row: Report, expires_at=None) -> ReportShareIssued:
        expiry = to_naive_utc(expires_at) if expires_at else utc_now() + timedelta(days=30)
        if expiry <= utc_now() or expiry > utc_now() + timedelta(days=365):
            raise HTTPException(status_code=422, detail="El vencimiento debe estar entre ahora y un año")
        token = secrets.token_urlsafe(32)
        link = ReportLink(report_id=row.id, token=hashlib.sha256(token.encode()).hexdigest(), access_mode="public", allow_download="false", expires_at=expiry, status="active")
        db.add(link)
        db.commit()
        db.refresh(link)
        return ReportShareIssued(id=link.id, token=token, expires_at=expiry)

    def public_report(self, db: Session, token: str) -> CatalogReportResult:
        if len(token) > 120:
            raise _not_found()
        digest = hashlib.sha256(token.encode()).hexdigest()
        link = db.query(ReportLink).filter(ReportLink.token == digest, ReportLink.access_mode == "public", ReportLink.status == "active").first()
        if link is None or (link.expires_at and link.expires_at <= utc_now()):
            raise _not_found()
        return self.resolve(db, self.get(db, link.report_id))

    def links(self, db: Session, report_id: str) -> list[ReportShareRead]:
        rows = db.query(ReportLink).filter(ReportLink.report_id == report_id, ReportLink.access_mode == "public").order_by(ReportLink.created_at.desc()).all()
        return [ReportShareRead(id=row.id, expires_at=row.expires_at, status="expired" if row.expires_at and row.expires_at <= utc_now() else row.status) for row in rows]

    def revoke(self, db: Session, report_id: str, link_id: str) -> ReportShareRead:
        link = db.query(ReportLink).filter(ReportLink.id == link_id, ReportLink.report_id == report_id, ReportLink.access_mode == "public").first()
        if link is None:
            raise _not_found()
        link.status = "revoked"
        db.commit()
        return ReportShareRead(id=link.id, expires_at=link.expires_at, status=link.status)


report_catalog_service = ReportCatalogService()
