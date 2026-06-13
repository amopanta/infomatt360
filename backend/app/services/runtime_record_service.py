"""
Proyecto: InfoMatt360
Modulo: Runtime Record Service
Responsabilidad: Aplicar reglas de negocio para guardar y consultar capturas Runtime.
Dependencias: SQLAlchemy Session, modelos RuntimeRecord y RuntimeRecordValue.
Notas: El servicio no contiene logica HTTP; los routers solo exponen la API.
"""

from sqlalchemy.orm import Session

from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.runtime_record import RuntimeRecordCreate, RuntimeRecordRead, RuntimeValueRead


def value_to_read(row: RuntimeRecordValue) -> RuntimeValueRead:
    """Convierte un valor ORM en contrato de salida API."""
    return RuntimeValueRead(
        id=row.id,
        record_id=row.record_id,
        component_id=row.component_id,
        field_name=row.field_name,
        field_value_json=row.field_value_json,
    )


def record_to_read(db: Session, row: RuntimeRecord) -> RuntimeRecordRead:
    """Convierte la cabecera y sus valores en una respuesta consolidada."""
    values = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == row.id).all()
    return RuntimeRecordRead(
        id=row.id,
        project_id=row.project_id,
        template_id=row.template_id,
        version_id=row.version_id,
        status=row.status,
        submitted_by=row.submitted_by,
        device_id=row.device_id,
        ip_address=row.ip_address,
        values=[value_to_read(item) for item in values],
    )


class RuntimeRecordService:
    """Reglas de negocio de persistencia Runtime."""

    def save_record(self, db: Session, payload: RuntimeRecordCreate, user_id: str | None) -> RuntimeRecordRead:
        """Guarda una captura Runtime completa en una unica transaccion logica.

        Crea primero la cabecera y luego cada valor capturado. El diseno es
        flexible para soportar campos simples y complejos sin migraciones por formulario.
        """
        record = RuntimeRecord(
            project_id=payload.project_id,
            template_id=payload.template_id,
            version_id=payload.version_id,
            status=payload.status,
            submitted_by=user_id,
            device_id=payload.device_id,
            ip_address=payload.ip_address,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        for item in payload.values:
            db.add(
                RuntimeRecordValue(
                    record_id=record.id,
                    component_id=item.component_id,
                    field_name=item.field_name,
                    field_value_json=item.field_value_json,
                )
            )
        db.commit()
        return record_to_read(db, record)

    def get_record(self, db: Session, record_id: str) -> RuntimeRecordRead | None:
        """Consulta una captura por identificador."""
        row = db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id).first()
        return record_to_read(db, row) if row else None

    def list_template_records(self, db: Session, template_id: str) -> list[RuntimeRecordRead]:
        """Lista capturas asociadas a una plantilla Runtime."""
        rows = db.query(RuntimeRecord).filter(RuntimeRecord.template_id == template_id).order_by(RuntimeRecord.created_at.desc()).all()
        return [record_to_read(db, row) for row in rows]


runtime_record_service = RuntimeRecordService()
