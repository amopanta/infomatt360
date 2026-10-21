"""Regresión: las observaciones no contaminan las respuestas exportadas."""
from types import SimpleNamespace as Row

from app.services.review_export_service import clean_answer_rows, review_observation_rows


def test_clean_export_has_no_review_fields_and_no_duplicate_rows():
    record = Row(id="r1", project_id="p1", template_id="t1", participant_id="f1")
    values = {"r1": [Row(field_name="edad", field_value_json="36")]}
    actions = [
        Row(id="a1", record_id="r1", project_id="p1", rejected_field_name="edad",
            notes="Revisar edad", user_id="u1", action="return",
            from_status="submitted", to_status="returned", created_at=None),
        Row(id="a2", record_id="r1", project_id="p1", rejected_field_name="edad",
            notes="Revisar documento", user_id="u1", action="return",
            from_status="submitted", to_status="returned", created_at=None),
    ]
    answers = clean_answer_rows([record], values)
    observations = review_observation_rows(actions)
    assert answers == [{"record_id": "r1", "project_id": "p1", "template_id": "t1",
                        "participant_id": "f1", "answer:edad": 36}]
    assert len(observations) == 2
    assert all("observation" not in row for row in answers)
