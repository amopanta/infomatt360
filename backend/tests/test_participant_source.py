import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.builder import BuilderTemplate
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.models.form_lookup import FormLookup
from app.schemas.builder import ParticipantSource
from app.services.participant_source_service import eligible_participants, ensure_eligible, validate_source


def test_named_participant_group_limits_form_capture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        form = BuilderTemplate(id="group-form", project_id="project", name="Visita")
        db.add_all([form, Participant(id="p1", project_id="project", full_name="Uno", metadata_json='{"group_name":"Familias de Soacha"}'), Participant(id="p2", project_id="project", full_name="Dos")])
        db.commit()
        form.participant_source_json = ParticipantSource(mode="group", group_name="Familias de Soacha").model_dump_json()
        assert [person.id for person in eligible_participants(db, form)] == ["p1"]
        with pytest.raises(ValueError, match="no cumple"):
            ensure_eligible(db, form, "p2")


def test_previous_form_requires_matching_participant_and_status():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        before = BuilderTemplate(id="before", project_id="project", name="Visita 2")
        after = BuilderTemplate(id="after", project_id="project", name="Visita 3")
        first = Participant(id="p1", project_id="project", full_name="Uno")
        second = Participant(id="p2", project_id="project", full_name="Dos")
        db.add_all([before, after, first, second, RuntimeRecord(id="r1", project_id="project", template_id="before", participant_id="p1", status="completed"), RuntimeRecord(id="r2", project_id="project", template_id="before", participant_id="p2", status="submitted")])
        db.commit()
        source = ParticipantSource(mode="form", previous_template_id="before", required_status="completed")
        validate_source(db, after, source)
        after.participant_source_json = source.model_dump_json()
        assert [person.id for person in eligible_participants(db, after)] == ["p1"]
        ensure_eligible(db, after, "p1")
        with pytest.raises(ValueError, match="no cumple"):
            ensure_eligible(db, after, "p2")
        with pytest.raises(ValueError, match="requiere"):
            ensure_eligible(db, after, None)


def test_pull_group_matches_participant_external_code():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        form = BuilderTemplate(id="form-pull", project_id="project", name="Visita")
        db.add_all([form, Participant(id="p1", project_id="project", full_name="Uno", external_code="001"), Participant(id="p2", project_id="project", full_name="Dos", external_code="002"), FormLookup(project_id="project", template_id=form.id, name="familias", columns_json='["codigo", "nombre"]', rows_json='[{"codigo":"001","nombre":"Uno"}]', row_count=1, checksum="abc")])
        db.commit()
        source = ParticipantSource(mode="pull", pull_name="familias", pull_key_column="codigo")
        validate_source(db, form, source)
        form.participant_source_json = source.model_dump_json()
        assert [person.id for person in eligible_participants(db, form)] == ["p1"]
        with pytest.raises(ValueError, match="no cumple"):
            ensure_eligible(db, form, "p2")
