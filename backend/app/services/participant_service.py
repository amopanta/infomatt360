from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.builder import BuilderTemplate
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.participants import ParticipantCreate, ParticipantHistoryItem, ParticipantRead


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

    def get_participant(self, db: Session, participant_id: str, project_id: str | None = None) -> ParticipantRead | None:
        query = db.query(Participant).filter(Participant.id == participant_id)
        if project_id:
            query = query.filter(Participant.project_id == project_id)
        row = query.first()
        return _to_read(row) if row else None

    def get_participant_history(self, db: Session, participant_id: str) -> list[ParticipantHistoryItem]:
        """Historial unificado del participante: el eje central de InfoMatt360 (ver docs/98).

        Recorre `RuntimeRecord.participant_id` (enlazado explicitamente o por
        coincidencia de documento en `runtime_record_service.save_record`) sin
        importar de que plantilla o canal vino cada captura.
        """
        records = db.query(RuntimeRecord).filter(RuntimeRecord.participant_id == participant_id).order_by(RuntimeRecord.created_at.desc()).all()
        template_ids = {record.template_id for record in records}
        template_names = {
            template.id: template.name
            for template in db.query(BuilderTemplate).filter(BuilderTemplate.id.in_(template_ids)).all()
        } if template_ids else {}
        return [
            ParticipantHistoryItem(
                record_id=record.id,
                template_id=record.template_id,
                template_name=template_names.get(record.template_id, "Formulario eliminado"),
                status=record.status,
                created_at=record.created_at,
                updated_at=record.updated_at,
                submitted_by=record.submitted_by,
            )
            for record in records
        ]


participant_service = ParticipantService()
