from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import to_naive_utc, utc_now
from app.models.builder import BuilderComponent, BuilderTemplate, BuilderVersion
from app.models.identity import User
from app.models.runtime_record import RuntimeRecord
from app.schemas.builder import BuilderComponentCreate, BuilderComponentPropertiesUpdate, BuilderComponentRead, BuilderTemplateCreate, BuilderTemplatePropertiesUpdate, BuilderTemplateRead, BuilderVersionCreate, BuilderVersionRead
from app.services.template_availability import availability


def template_to_read(row: BuilderTemplate, owner_name: str | None = None, submissions_count: int = 0) -> BuilderTemplateRead:
    """Convierte el modelo ORM de plantilla a esquema de salida."""
    state = availability(row)
    return BuilderTemplateRead(id=row.id, project_id=row.project_id, name=row.name, description=row.description, status=row.status, theme_json=row.theme_json, created_at=row.created_at, updated_at=row.updated_at or row.created_at, published_at=row.published_at, owner_name=owner_name, submissions_count=submissions_count, starts_at=row.starts_at, ends_at=row.ends_at, availability=state, accepting_responses=state == "accepting")


def component_to_read(row: BuilderComponent) -> BuilderComponentRead:
    """Convierte un componente visual a respuesta API."""
    return BuilderComponentRead(
        id=row.id,
        template_id=row.template_id,
        column_id=row.column_id,
        component_type=row.component_type,
        name=row.name,
        label=row.label,
        config_json=row.config_json,
        rules_json=row.rules_json,
        sort_order=row.sort_order,
    )


def version_to_read(row: BuilderVersion) -> BuilderVersionRead:
    """Convierte una version guardada a respuesta API."""
    return BuilderVersionRead(id=row.id, template_id=row.template_id, version_number=row.version_number, schema_json=row.schema_json, status=row.status)


class BuilderService:
    """Servicio base del constructor visual.

    Centraliza operaciones de plantillas, componentes y versiones para evitar
    que los routers contengan reglas de negocio.
    """

    def create_template(self, db: Session, payload: BuilderTemplateCreate, user_id: str | None = None) -> BuilderTemplateRead:
        now = utc_now()
        row = BuilderTemplate(**payload.model_dump(), created_by=user_id, updated_at=now, published_at=now if payload.status == "published" else None)
        db.add(row)
        db.commit()
        db.refresh(row)
        owner = db.get(User, user_id) if user_id else None
        return template_to_read(row, owner.full_name if owner else None)

    def list_templates(self, db: Session, project_id: str) -> list[BuilderTemplateRead]:
        rows = db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id).order_by(BuilderTemplate.created_at.desc()).all()
        if not rows:
            return []
        ids = [row.id for row in rows]
        counts = dict(db.query(RuntimeRecord.template_id, func.count(RuntimeRecord.id)).filter(RuntimeRecord.template_id.in_(ids)).group_by(RuntimeRecord.template_id).all())
        owner_ids = [row.created_by for row in rows if row.created_by]
        owners = {user.id: user.full_name for user in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
        return [template_to_read(row, owners.get(row.created_by), counts.get(row.id, 0)) for row in rows]

    def get_template(self, db: Session, template_id: str) -> BuilderTemplateRead:
        row = db.get(BuilderTemplate, template_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulario no encontrado")
        owner = db.get(User, row.created_by) if row.created_by else None
        count = db.query(func.count(RuntimeRecord.id)).filter(RuntimeRecord.template_id == row.id).scalar() or 0
        return template_to_read(row, owner.full_name if owner else None, count)

    def set_template_status(self, db: Session, template_id: str, new_status: str) -> BuilderTemplateRead:
        row = db.get(BuilderTemplate, template_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulario no encontrado")
        if new_status == "published" and not db.query(BuilderComponent.id).filter(BuilderComponent.template_id == template_id).first():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Agrega al menos una pregunta antes de publicar")
        if row.status == "archived" and new_status not in {"archived", "draft"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Restaura el formulario como borrador antes de publicarlo")
        if row.status != new_status:
            row.status = new_status
            row.updated_at = utc_now()
            if new_status == "published":
                row.published_at = row.updated_at
            db.commit()
            db.refresh(row)
        return self.get_template(db, template_id)

    def set_template_properties(self, db: Session, template_id: str, payload: BuilderTemplatePropertiesUpdate) -> BuilderTemplateRead:
        row = db.get(BuilderTemplate, template_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")
        row.name = payload.name.strip()
        if not row.name:
            raise HTTPException(status_code=422, detail="El nombre del formulario es obligatorio")
        row.description = payload.description.strip() if payload.description else None
        row.theme_json = payload.theme_json
        row.updated_at = utc_now()
        db.commit()
        return self.get_template(db, template_id)

    def set_template_schedule(self, db: Session, template_id: str, starts_at, ends_at) -> BuilderTemplateRead:
        row = db.get(BuilderTemplate, template_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulario no encontrado")
        start = to_naive_utc(starts_at)
        end = to_naive_utc(ends_at)
        if start is not None and end is not None and start >= end:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de finalizacion debe ser posterior al inicio")
        row.starts_at = start
        row.ends_at = end
        row.updated_at = utc_now()
        db.commit()
        return self.get_template(db, template_id)

    def add_component(self, db: Session, payload: BuilderComponentCreate) -> BuilderComponentRead:
        row = BuilderComponent(**payload.model_dump())
        db.add(row)
        template = db.get(BuilderTemplate, payload.template_id)
        if template is not None:
            template.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return component_to_read(row)

    def set_component_properties(self, db: Session, component_id: str, payload: BuilderComponentPropertiesUpdate) -> BuilderComponentRead:
        row = db.get(BuilderComponent, component_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Pregunta no encontrada")
        name = payload.name.strip()
        label = payload.label.strip()
        if not name or not label:
            raise HTTPException(status_code=422, detail="La etiqueta y el nombre técnico son obligatorios")
        if name != row.name:
            if db.query(RuntimeRecord.id).filter(RuntimeRecord.template_id == row.template_id).first():
                raise HTTPException(status_code=422, detail="El nombre técnico no se puede cambiar cuando ya hay respuestas; cambia la etiqueta visible")
            if db.query(BuilderComponent.id).filter(BuilderComponent.template_id == row.template_id, BuilderComponent.name == name, BuilderComponent.id != row.id).first():
                raise HTTPException(status_code=422, detail="Ya existe una pregunta con ese nombre técnico")
        row.name = name
        row.label = label
        row.config_json = payload.config_json
        template = db.get(BuilderTemplate, row.template_id)
        if template:
            template.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return component_to_read(row)

    def list_components(self, db: Session, template_id: str, column_id: str | None = None) -> list[BuilderComponentRead]:
        """Lista componentes de una plantilla, opcionalmente filtrados por columna."""
        query = db.query(BuilderComponent).filter(BuilderComponent.template_id == template_id)
        if column_id:
            query = query.filter(BuilderComponent.column_id == column_id)
        rows = query.order_by(BuilderComponent.sort_order).all()
        return [component_to_read(row) for row in rows]

    def create_version(self, db: Session, payload: BuilderVersionCreate) -> BuilderVersionRead:
        row = BuilderVersion(
            template_id=payload.template_id,
            version_number=payload.version_number,
            schema_json=payload.schema_content,
            status=payload.status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return version_to_read(row)


builder_service = BuilderService()
