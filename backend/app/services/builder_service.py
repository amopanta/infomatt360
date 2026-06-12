from sqlalchemy.orm import Session

from app.models.builder import BuilderComponent, BuilderTemplate, BuilderVersion
from app.schemas.builder import BuilderComponentCreate, BuilderComponentRead, BuilderTemplateCreate, BuilderTemplateRead, BuilderVersionCreate, BuilderVersionRead


def template_to_read(row: BuilderTemplate) -> BuilderTemplateRead:
    return BuilderTemplateRead(id=row.id, project_id=row.project_id, name=row.name, description=row.description, status=row.status)


def component_to_read(row: BuilderComponent) -> BuilderComponentRead:
    return BuilderComponentRead(id=row.id, template_id=row.template_id, component_type=row.component_type, name=row.name, label=row.label, config_json=row.config_json, rules_json=row.rules_json, sort_order=row.sort_order)


def version_to_read(row: BuilderVersion) -> BuilderVersionRead:
    return BuilderVersionRead(id=row.id, template_id=row.template_id, version_number=row.version_number, schema_json=row.schema_json, status=row.status)


class BuilderService:
    def create_template(self, db: Session, payload: BuilderTemplateCreate) -> BuilderTemplateRead:
        row = BuilderTemplate(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return template_to_read(row)

    def list_templates(self, db: Session, project_id: str) -> list[BuilderTemplateRead]:
        rows = db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id).order_by(BuilderTemplate.created_at.desc()).all()
        return [template_to_read(row) for row in rows]

    def add_component(self, db: Session, payload: BuilderComponentCreate) -> BuilderComponentRead:
        row = BuilderComponent(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return component_to_read(row)

    def create_version(self, db: Session, payload: BuilderVersionCreate) -> BuilderVersionRead:
        row = BuilderVersion(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return version_to_read(row)


builder_service = BuilderService()
