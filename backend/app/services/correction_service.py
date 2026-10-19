"""Devoluciones con destinatario y observaciones por pregunta (docs/141).

Reglas:
- Un registro devuelto lo corrige SOLO su destinatario: la persona asignada
  por el revisor o, si no se asignó, el autor original. El autor
  (submitted_by) nunca cambia.
- Enviado, en revisión y aprobado son de solo lectura; la edición posterior
  exige una devolución formal (o la reapertura administrativa).
- Las observaciones se guardan aparte de las respuestas y tienen su propio
  ciclo: pending → in_correction → corrected → verified | rejected.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.permissions import get_project_permissions, participant_visible
from app.core.permissions import RECORDS_WRITE
from app.core.time import utc_now
from app.models.assignment import UserProjectAssignment
from app.models.files import FileAsset
from app.models.messages import InternalMessage
from app.models.participants import Participant
from app.models.review import ReviewObservation
from app.models.runtime_record import RuntimeRecord
from app.schemas.review import ReviewActionCreate

EDITABLE_STATUSES = {"draft", "returned", "corrected"}
OBSERVATION_STATUSES = {"pending", "in_correction", "corrected", "verified", "rejected"}
# Quién puede mover una observación a cada estado
GESTOR_STATUSES = {"in_correction", "corrected"}
REVIEWER_STATUSES = {"verified", "rejected", "pending"}


def correction_recipient(record: RuntimeRecord) -> str | None:
    return record.correction_user_id or record.submitted_by


def ensure_can_edit(record: RuntimeRecord, user_id: str | None) -> None:
    if record.status not in EDITABLE_STATUSES:
        raise ValueError(f"El registro en estado '{record.status}' no admite edición; solicita una devolución para corregirlo")
    if record.status in {"returned", "corrected"} and user_id != correction_recipient(record):
        raise PermissionError("Solo la persona designada para corregir puede editar este registro")
    if record.status == "draft" and record.submitted_by and user_id != record.submitted_by:
        raise PermissionError("Solo el autor puede editar su borrador")


def validate_assignee(db: Session, record: RuntimeRecord, assignee_user_id: str) -> None:
    """El destinatario debe poder capturar en el proyecto y ver al participante."""
    active = db.query(UserProjectAssignment).filter_by(user_id=assignee_user_id, project_id=record.project_id, status="active").first()
    _, permissions = get_project_permissions(db, assignee_user_id, record.project_id)
    if active is None and RECORDS_WRITE not in permissions:
        raise ValueError("El destinatario no tiene acceso al proyecto")
    if RECORDS_WRITE not in permissions:
        raise ValueError("El destinatario no tiene permiso para capturar en el proyecto")
    if record.participant_id:
        participant = db.get(Participant, record.participant_id)
        if participant is not None and not participant_visible(db, assignee_user_id, participant):
            raise ValueError("El participante está fuera del territorio del destinatario")


def _observation_rows(db: Session, record: RuntimeRecord, actor_id: str, action_id: str | None, observations: list[dict]) -> list[ReviewObservation]:
    created: list[ReviewObservation] = []
    now = utc_now()
    for item in observations:
        reason = str(item.get("reason") or "").strip()
        if not reason:
            raise ValueError("Cada observación necesita un motivo")
        evidence_id = item.get("evidence_file_id")
        if evidence_id:
            asset = db.get(FileAsset, evidence_id)
            if asset is None or asset.project_id != record.project_id:
                raise ValueError("La evidencia de la observación no pertenece al proyecto")
        client_ref = item.get("client_ref")
        if client_ref:
            existing = db.query(ReviewObservation).filter_by(record_id=record.id, client_ref=client_ref).first()
            if existing is not None:
                created.append(existing)
                continue
        row = ReviewObservation(
            project_id=record.project_id, record_id=record.id, review_action_id=action_id,
            field_name=(item.get("field_name") or None), repeat_path=(item.get("repeat_path") or None),
            evidence_file_id=evidence_id or None, reason=reason[:4000],
            requested_action=(item.get("requested_action") or None), status="pending",
            created_by=actor_id, client_ref=client_ref, created_at=now, updated_at=now,
        )
        db.add(row)
        created.append(row)
    return created


def return_record(db: Session, record: RuntimeRecord, actor_id: str, notes: str, assignee_user_id: str | None,
                  observations: list[dict], apply_action) -> tuple[object, list[ReviewObservation]]:
    """Devuelve el registro (vía review_service.apply_action, que valida la
    transición y el flujo), fija el destinatario y crea las observaciones."""
    if assignee_user_id:
        validate_assignee(db, record, assignee_user_id)
    action = apply_action(db, ReviewActionCreate(project_id=record.project_id, record_id=record.id, to_status="returned",
                                                 action="return", notes=notes,
                                                 rejected_field_name=(observations[0].get("field_name") if observations else None)), actor_id)
    record = db.get(RuntimeRecord, record.id)
    record.correction_user_id = assignee_user_id if assignee_user_id and assignee_user_id != record.submitted_by else None
    record.returned_at = utc_now()
    rows = _observation_rows(db, record, actor_id, action.id, observations)
    recipient = correction_recipient(record)
    if recipient and recipient != record.submitted_by:
        db.add(InternalMessage(project_id=record.project_id, sender_id=actor_id, recipient_id=recipient,
                               subject="Corrección asignada", body=f"Se le asignó la corrección de un registro. Motivo: {notes}"[:2000]))
    db.commit()
    for row in rows:
        db.refresh(row)
    return action, rows


def update_observation(db: Session, observation: ReviewObservation, user_id: str, status: str, note: str | None, *, is_reviewer: bool) -> ReviewObservation:
    if status not in OBSERVATION_STATUSES:
        raise ValueError("Estado de observación no válido")
    record = db.get(RuntimeRecord, observation.record_id)
    if status in GESTOR_STATUSES:
        if record is None or user_id != correction_recipient(record):
            raise PermissionError("Solo la persona designada para corregir puede marcar la observación")
    elif not is_reviewer:
        raise PermissionError("Solo un revisor puede verificar o rechazar la corrección")
    observation.status = status
    if note is not None:
        observation.response_note = note.strip()[:4000] or None
    observation.resolved_by = user_id if status in {"verified", "rejected"} else observation.resolved_by
    observation.updated_at = utc_now()
    db.commit()
    db.refresh(observation)
    return observation


def observation_to_dict(row: ReviewObservation) -> dict:
    return {
        "id": row.id, "record_id": row.record_id, "review_action_id": row.review_action_id,
        "field_name": row.field_name, "repeat_path": row.repeat_path, "evidence_file_id": row.evidence_file_id,
        "reason": row.reason, "requested_action": row.requested_action, "status": row.status,
        "response_note": row.response_note, "created_by": row.created_by, "resolved_by": row.resolved_by,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def correction_package(db: Session, record: RuntimeRecord, values: list, files: list[FileAsset]) -> dict:
    """Lo que necesita una tablet para corregir (docs/141 §7): respuestas,
    versión, observaciones y manifiesto de adjuntos (para no bajar de nuevo
    lo que ya tiene)."""
    observations = db.query(ReviewObservation).filter(ReviewObservation.record_id == record.id).order_by(ReviewObservation.created_at).all()
    return {
        "record_id": record.id, "project_id": record.project_id, "template_id": record.template_id,
        "participant_id": record.participant_id, "status": record.status, "lock_version": record.lock_version,
        "content_hash": record.content_hash, "author_id": record.submitted_by,
        "correction_user_id": correction_recipient(record), "returned_at": _iso(record.returned_at),
        "values": [{"field_name": v.field_name, "field_value_json": v.field_value_json} for v in values],
        "observations": [{**observation_to_dict(o), "created_at": _iso(o.created_at), "updated_at": _iso(o.updated_at)} for o in observations],
        "attachments": [{"file_asset_id": f.id, "name": f.original_name, "mime_type": f.mime_type, "size_bytes": f.size_bytes, "checksum": f.checksum} for f in files],
    }


def serialize(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
