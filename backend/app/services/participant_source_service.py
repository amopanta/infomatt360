"""Eligibility rules for a form's participant source."""

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.builder import BuilderTemplate
from app.models.participants import Participant
from app.models.form_lookup import FormLookup
from app.models.runtime_record import RuntimeRecord
from app.schemas.builder import ParticipantSource


def configured_source(template: BuilderTemplate) -> ParticipantSource:
    return ParticipantSource.model_validate_json(template.participant_source_json) if template.participant_source_json else ParticipantSource()


def participant_municipality(participant: Participant) -> str:
    try:
        metadata = json.loads(participant.metadata_json or "{}")
    except ValueError:
        return ""
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("municipality") or metadata.get("municipio") or "").strip().casefold()


def validate_source(db: Session, template: BuilderTemplate, source: ParticipantSource) -> None:
    if source.mode == "list":
        count = db.query(Participant.id).filter(Participant.project_id == template.project_id, Participant.id.in_(source.participant_ids)).count()
        if count != len(set(source.participant_ids)):
            raise HTTPException(status_code=422, detail="La lista contiene participantes de otro proyecto o inexistentes")
    if source.mode == "form":
        previous = db.get(BuilderTemplate, source.previous_template_id)
        if previous is None or previous.project_id != template.project_id or previous.id == template.id:
            raise HTTPException(status_code=422, detail="Selecciona otro formulario del mismo proyecto")
    if source.mode == "pull":
        lookup = db.query(FormLookup).filter(FormLookup.template_id == template.id, FormLookup.name == source.pull_name).first()
        if lookup is None or source.pull_key_column not in json.loads(lookup.columns_json):
            raise HTTPException(status_code=422, detail="El grupo Pull o la columna de relación no existe en este formulario")


def eligible_participants(db: Session, template: BuilderTemplate) -> list[Participant]:
    source = configured_source(template)
    rows = db.query(Participant).filter(Participant.project_id == template.project_id, Participant.status == "active").all()
    if source.mode == "list":
        allowed = set(source.participant_ids)
        return [item for item in rows if item.id in allowed]
    if source.mode == "group":
        wanted = (source.group_name or "").strip().casefold()
        result = []
        for item in rows:
            try:
                metadata = json.loads(item.metadata_json or "{}")
            except ValueError:
                metadata = {}
            if isinstance(metadata, dict) and str(metadata.get("group_name") or "").strip().casefold() == wanted:
                result.append(item)
        return result
    if source.mode == "filter":
        wanted = (source.municipality or "").strip().casefold()
        return [item for item in rows if participant_municipality(item) == wanted]
    if source.mode == "form":
        found = db.query(RuntimeRecord.participant_id).filter(
            RuntimeRecord.project_id == template.project_id,
            RuntimeRecord.template_id == source.previous_template_id,
            RuntimeRecord.status == source.required_status,
            RuntimeRecord.participant_id.isnot(None),
        ).distinct().all()
        allowed = {participant_id for (participant_id,) in found}
        return [item for item in rows if item.id in allowed]
    if source.mode == "pull":
        lookup = db.query(FormLookup).filter(FormLookup.template_id == template.id, FormLookup.name == source.pull_name).first()
        if lookup is None:
            return []
        allowed = {str(item.get(source.pull_key_column, "")).strip() for item in json.loads(lookup.rows_json)}
        return [item for item in rows if str(getattr(item, source.participant_key_field) or "").strip() in allowed]
    return rows


def ensure_eligible(db: Session, template: BuilderTemplate, participant_id: str | None) -> None:
    source = configured_source(template)
    if source.mode == "all":
        return
    if not participant_id:
        raise ValueError("Este formulario requiere seleccionar un participante elegible")
    if participant_id not in {item.id for item in eligible_participants(db, template)}:
        raise ValueError("El participante no cumple la fuente configurada para este formulario")
