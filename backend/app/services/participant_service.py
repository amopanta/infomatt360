from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.participants import Participant
from app.schemas.participants import ParticipantCreate, ParticipantRead


def _to_read(row: Participant) -> ParticipantRead:
    return ParticipantRead(
        id=row.id,
        project_id=row.project_id,
        external_code=row.external_code,
        document_id=row.document_id,
        full_name=row.full_name,
        participant_type=row.participant_type,
        status=row.status,
        duplicate_flag=row.duplicate_flag,
        metadata_json=row.metadata_json,
    )


class ParticipantService:
    def create_participant(self, db: Session, payload: ParticipantCreate) -> ParticipantRead:
        if payload.document_id:
            duplicate = db.query(Participant).filter(
                Participant.project_id == payload.project_id,
                Participant.document_id == payload.document_id,
            ).first()
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un participante con este documento en el proyecto",
                )
        row = Participant(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def list_participants(self, db: Session, project_id: str) -> list[ParticipantRead]:
        rows = db.query(Participant).filter(Participant.project_id == project_id).order_by(Participant.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def get_participant(self, db: Session, participant_id: str) -> ParticipantRead | None:
        row = db.query(Participant).filter(Participant.id == participant_id).first()
        return _to_read(row) if row else None


participant_service = ParticipantService()
