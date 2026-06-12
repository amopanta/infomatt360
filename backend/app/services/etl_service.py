from sqlalchemy.orm import Session

from app.models.etl import EtlPipeline, EtlRule
from app.schemas.etl import EtlPipelineCreate, EtlPipelineRead, EtlRuleCreate, EtlRuleRead


def rule_to_read(row: EtlRule) -> EtlRuleRead:
    return EtlRuleRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        rule_type=row.rule_type,
        source_field=row.source_field,
        target_field=row.target_field,
        operator=row.operator,
        value_text=row.value_text,
        config_json=row.config_json,
        status=row.status,
    )


def pipeline_to_read(row: EtlPipeline) -> EtlPipelineRead:
    return EtlPipelineRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        source_id=row.source_id,
        steps_json=row.steps_json,
        status=row.status,
    )


class EtlService:
    def create_rule(self, db: Session, payload: EtlRuleCreate) -> EtlRuleRead:
        row = EtlRule(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return rule_to_read(row)

    def list_rules(self, db: Session, project_id: str) -> list[EtlRuleRead]:
        rows = db.query(EtlRule).filter(EtlRule.project_id == project_id).order_by(EtlRule.created_at.desc()).all()
        return [rule_to_read(row) for row in rows]

    def create_pipeline(self, db: Session, payload: EtlPipelineCreate) -> EtlPipelineRead:
        row = EtlPipeline(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return pipeline_to_read(row)

    def list_pipelines(self, db: Session, project_id: str) -> list[EtlPipelineRead]:
        rows = db.query(EtlPipeline).filter(EtlPipeline.project_id == project_id).order_by(EtlPipeline.created_at.desc()).all()
        return [pipeline_to_read(row) for row in rows]


etl_service = EtlService()
