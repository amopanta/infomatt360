import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.builder import BuilderTemplate
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.builder import ParticipantSource
from app.services.participant_source_service import eligible_participants, ensure_eligible, validate_source


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
