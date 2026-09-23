from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.models.form_lookup import FormLookup
from app.models.runtime_record import RuntimeRecord
from app.services.builder_service import builder_service


def test_duplicate_form_copies_layout_and_pull_without_responses():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        form = BuilderTemplate(id="source", project_id="project", name="Visita", status="published")
        page = BuilderPage(id="page", template_id=form.id, title="Inicio")
        section = BuilderSection(id="section", page_id=page.id, title="Datos")
        row = BuilderRow(id="row", section_id=section.id)
        column = BuilderColumn(id="column", row_id=row.id)
        db.add_all([form, page, section, row, column,
                    BuilderComponent(template_id=form.id, column_id=column.id, component_type="TEXT", name="nombre", label="Nombre"),
                    FormLookup(project_id="project", template_id=form.id, name="familias", columns_json='["codigo","nombre"]', rows_json='[{"codigo":"1","nombre":"Ana"}]', row_count=1, checksum="abc"),
                    RuntimeRecord(id="answer", project_id="project", template_id=form.id, status="submitted")])
        db.commit()
        copy = builder_service.duplicate_template(db, form.id, "user")
        assert copy.id != form.id
        assert copy.status == "draft"
        assert db.query(RuntimeRecord).filter_by(template_id=copy.id).count() == 0
        new_component = db.query(BuilderComponent).filter_by(template_id=copy.id).one()
        assert new_component.name == "nombre" and new_component.column_id != column.id
        assert db.query(FormLookup).filter_by(template_id=copy.id, name="familias").count() == 1
