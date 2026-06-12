from sqlalchemy.orm import Session

from app.models.records import Record, RecordEvent
from app.schemas.records import RecordCreate, RecordEventRead, RecordRead


def _to_read(row: Record) -> RecordRead:
    return RecordRead(
        id=row.id,
        project_id=row.project_id,
        form_id=row.form_id,
        participant_id=row.participant_id,
        status=row.status,
        source_channel=row.source_channel,
        payload_json=row.payload_json,
        created_by=row.created_by,
    )


def _event_to_read(row: RecordEvent) -> RecordEventRead:
    return RecordEventRead(
        id=row.id,
        record_id=row.record_id,
        event_type=row.event_type,
        user_id=row.user_id,
        notes=row.notes,
    )


class RecordService:
    def create_record(self, db: Session, payload: RecordCreate, user_id: str) -> RecordRead:
        row = Record(**payload.model_dump(), created_by=user_id, updated_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)

        event = RecordEvent(record_id=row.id, event_type="created", user_id=user_id, notes="Registro creado")
        db.add(event)
        db.commit()
        return _to_read(row)

    def list_records(self, db: Session, project_id: str, participant_id: str | None = None) -> list[RecordRead]:
        query = db.query(Record).filter(Record.project_id == project_id)
        if participant_id:
            query = query.filter(Record.participant_id == participant_id)
        rows = query.order_by(Record.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def list_record_events(self, db: Session, record_id: str) -> list[RecordEventRead]:
        rows = db.query(RecordEvent).filter(RecordEvent.record_id == record_id).order_by(RecordEvent.created_at.desc()).all()
        return [_event_to_read(row) for row in rows]


record_service = RecordService()
