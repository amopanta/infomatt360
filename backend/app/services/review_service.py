from sqlalchemy.orm import Session

from app.models.records import Record, RecordEvent
from app.models.review import ReviewAction
from app.schemas.review import ReviewActionCreate, ReviewActionRead


def to_read(row: ReviewAction) -> ReviewActionRead:
    return ReviewActionRead(
        id=row.id,
        project_id=row.project_id,
        record_id=row.record_id,
        from_status=row.from_status,
        to_status=row.to_status,
        action=row.action,
        notes=row.notes,
        user_id=row.user_id,
    )


class ReviewService:
    def apply_action(self, db: Session, payload: ReviewActionCreate, user_id: str) -> ReviewActionRead:
        record = db.query(Record).filter(Record.id == payload.record_id).first()
        from_status = record.status if record else None

        if record:
            record.status = payload.to_status
            record.updated_by = user_id

        row = ReviewAction(
            project_id=payload.project_id,
            record_id=payload.record_id,
            from_status=from_status,
            to_status=payload.to_status,
            action=payload.action,
            notes=payload.notes,
            user_id=user_id,
        )
        db.add(row)
        db.add(RecordEvent(record_id=payload.record_id, event_type=payload.action, user_id=user_id, notes=payload.notes))
        db.commit()
        db.refresh(row)
        return to_read(row)

    def list_actions(self, db: Session, record_id: str) -> list[ReviewActionRead]:
        rows = db.query(ReviewAction).filter(ReviewAction.record_id == record_id).order_by(ReviewAction.created_at.desc()).all()
        return [to_read(row) for row in rows]


review_service = ReviewService()
