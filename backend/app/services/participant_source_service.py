"""Eligibility rules for a form's participant source."""

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.builder import BuilderTemplate
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.builder import ParticipantSource


def configured_source(template: BuilderTemplate) -> ParticipantSource:
    return ParticipantSource.model_validate_json(template.participant_source_json) if template.participant_source_json else ParticipantSource()


def validate_source(db: Session, template: BuilderTemplate, source: ParticipantSource) -> None:
    if source.mode == "list":
        count = db.query(Participant.id).filter(Participant.project_id == template.project_id, Participant.id.in_(source.participant_ids)).count()
        if count != len(set(source.participant_ids)):
            raise HTTPException(status_code=422, detail="La lista contiene participantes de otro proyecto o inexistentes")
    if source.mode == "form":
        previous = db.get(BuilderTemplate, source.previous_template_id)
        if previous is None or previous.project_id != template.project_id or previous.id == template.id:
            raise HTTPException(status_code=422, detail="Selecciona otro formulario del mismo proyecto")


def eligible_participants(db: Session, template: BuilderTemplate) -> list[Participant]:
    source = configured_source(template)
    rows = db.query(Participant).filter(Participant.project_id == template.project_id, Participant.status == "active").all()
    if source.mode == "list":
        allowed = set(source.participant_ids)
        return [item for item in rows if item.id in allowed]
    if source.mode == "filter":
        wanted = (source.municipality or "").strip().casefold()
        return [item for item in rows if str(json.loads(item.metadata_json or "{}").get("municipality", "")).strip().casefold() == wanted]
    if source.mode == "form":
        found = db.query(RuntimeRecord.participant_id).filter(
            RuntimeRecord.project_id == template.project_id,
            RuntimeRecord.template_id == source.previous_template_id,
            RuntimeRecord.status == source.required_status,
            RuntimeRecord.participant_id.isnot(None),
        ).distinct().all()
        allowed = {participant_id for (participant_id,) in found}
        return [item for item in rows if item.id in allowed]
    return rows


def ensure_eligible(db: Session, template: BuilderTemplate, participant_id: str | None) -> None:
    source = configured_source(template)
    if source.mode == "all":
        return
    if not participant_id:
        raise ValueError("Este formulario requiere seleccionar un participante elegible")
    if participant_id not in {item.id for item in eligible_participants(db, template)}:
        raise ValueError("El participante no cumple la fuente configurada para este formulario")
