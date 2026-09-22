"""Aggregated report for one form, with no respondent-level values."""

import json
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.form_report import FormReportChoice, FormReportMonth, FormReportQuestion, FormReportRead
from app.services.report_service import NUMERIC_AGGREGATABLE_TYPES


CATEGORICAL_TYPES = {"BOOLEAN", "SELECT", "MULTISELECT", "DROPDOWN", "LIKERT_5", "LIKERT_7", "RATING", "NPS", "RANKING"}


class FormReportService:
    def resolve(self, db: Session, template: BuilderTemplate) -> FormReportRead:
        records = db.query(RuntimeRecord.id, RuntimeRecord.status, RuntimeRecord.created_at).filter(RuntimeRecord.project_id == template.project_id, RuntimeRecord.template_id == template.id, RuntimeRecord.status != "draft").order_by(RuntimeRecord.created_at).all()
        record_ids = [row.id for row in records]
        components = db.query(BuilderComponent).filter(BuilderComponent.template_id == template.id).order_by(BuilderComponent.sort_order, BuilderComponent.created_at).all()
        by_field: dict[str, dict[str, object]] = defaultdict(dict)
        if record_ids and components:
            for offset in range(0, len(record_ids), 500):
                values = db.query(RuntimeRecordValue.record_id, RuntimeRecordValue.field_name, RuntimeRecordValue.field_value_json).filter(RuntimeRecordValue.record_id.in_(record_ids[offset:offset + 500])).order_by(RuntimeRecordValue.created_at, RuntimeRecordValue.id).all()
                for record_id, field_name, raw in values:
                    try:
                        by_field[field_name][record_id] = json.loads(raw)
                    except (TypeError, ValueError):
                        by_field[field_name][record_id] = raw

        questions = []
        seen_names = set()
        for component in components:
            if component.name in seen_names:
                continue
            seen_names.add(component.name)
            values = [by_field[component.name].get(record_id) for record_id in record_ids]
            answered_values = [value for value in values if value is not None and value != "" and value != []]
            counts: Counter[str] = Counter()
            if component.component_type in CATEGORICAL_TYPES:
                for value in answered_values:
                    choices = value if isinstance(value, list) else [value]
                    for choice in choices:
                        if isinstance(choice, (str, int, float, bool)):
                            counts[str(choice)] += 1
            numeric = [float(value) for value in answered_values if isinstance(value, (int, float)) and not isinstance(value, bool)] if component.component_type in NUMERIC_AGGREGATABLE_TYPES else []
            questions.append(FormReportQuestion(
                name=component.name,
                label=component.label,
                field_type=component.component_type,
                answered=len(answered_values),
                missing=len(records) - len(answered_values),
                choices=[FormReportChoice(label=label, count=count) for label, count in counts.most_common(12)],
                numeric_min=min(numeric) if numeric else None,
                numeric_max=max(numeric) if numeric else None,
                numeric_average=round(sum(numeric) / len(numeric), 2) if numeric else None,
            ))

        statuses = Counter(row.status for row in records)
        months = Counter(row.created_at.strftime("%Y-%m") for row in records)
        return FormReportRead(
            template_id=template.id,
            template_name=template.name,
            description=template.description,
            status=template.status,
            records_total=len(records),
            records_by_status=dict(statuses),
            last_record_at=records[-1].created_at if records else None,
            months=[FormReportMonth(month=month, count=count) for month, count in sorted(months.items())],
            questions=questions,
        )


form_report_service = FormReportService()
