import csv
import json
from datetime import datetime
from io import StringIO

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.builder import BuilderTemplate
from app.models.case_management import ParticipantCase, SavedExport, SavedExportFile
from app.models.messages import InternalMessage
from app.api.permissions import allowed_participant_ids
from app.services.report_service import report_service
from app.services.runtime_record_service import runtime_record_service

MAX_EXPORT_BYTES = 25 * 1024 * 1024


def run_saved_export(db: Session, export: SavedExport) -> SavedExportFile:
    allowed = allowed_participant_ids(db, export.recipient_user_id, export.project_id)
    kind = export.export_kind or ("form" if export.template_id else "summary")
    if kind == "cases":
        query = db.query(ParticipantCase).filter(ParticipantCase.project_id == export.project_id)
        if allowed is not None:
            query = query.filter(ParticipantCase.participant_id.in_(allowed))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "participant_id", "case_type", "parent_case_id", "title", "status",
                         "assigned_user_id", "due_at", "properties_json", "updated_at"])
        for row in query.order_by(ParticipantCase.created_at, ParticipantCase.id).all():
            writer.writerow([row.id, row.participant_id, row.case_type, row.parent_case_id, row.title,
                             row.status, row.assigned_user_id, row.due_at.isoformat() if row.due_at else "",
                             json.dumps(json.loads(row.properties_json or "{}"), ensure_ascii=False), row.updated_at.isoformat()])
        content = output.getvalue().encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
    elif kind == "form":
        template = db.get(BuilderTemplate, export.template_id)
        if template is None or template.project_id != export.project_id:
            raise HTTPException(status_code=422, detail="El formulario guardado no pertenece al proyecto")
        content = runtime_record_service.export_template_csv(db, export.template_id, allowed_participant_ids=allowed).encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
    elif kind == "summary":
        if allowed is not None:
            raise HTTPException(status_code=403, detail="El resumen general no está disponible para usuarios con acceso territorial limitado")
        content = report_service.export_project_summary_xlsx(db, export.project_id)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=422, detail="Tipo de exportación desconocido")
    if len(content) > MAX_EXPORT_BYTES:
        raise HTTPException(status_code=413, detail="La exportación supera 25 MB")
    file = SavedExportFile(export_id=export.id, content=content, media_type=media_type)
    db.add(file)
    export.last_run_at = datetime.utcnow()
    db.add(InternalMessage(project_id=export.project_id, recipient_id=export.recipient_user_id,
                           subject=f"Exportación lista: {export.name}",
                           body=f"La exportación programada está disponible en Reportes → Exportaciones guardadas ({file.id})."))
    db.commit()
    db.refresh(file)
    old_ids = [row.id for row in db.query(SavedExportFile.id).filter(SavedExportFile.export_id == export.id)
               .order_by(SavedExportFile.created_at.desc(), SavedExportFile.id.desc()).offset(20).all()]
    if old_ids:
        db.query(SavedExportFile).filter(SavedExportFile.id.in_(old_ids)).delete(synchronize_session=False)
        db.commit()
    return file
