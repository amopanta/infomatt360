from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import allowed_participant_ids, get_project_permissions, require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, REPORTS_EXPORT
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.case_management import SavedExport, SavedExportFile, UserTerritory
from app.models.identity import User
from app.models.scheduler import ScheduledTask
from app.schemas.case_management import SavedExportCreate, SavedExportRead
from app.services.assignment_service import assignment_service
from app.services.saved_export_service import run_saved_export

router = APIRouter()


def _export(db: Session, user: User, export_id: str) -> SavedExport:
    row = db.get(SavedExport, export_id)
    if not row:
        raise HTTPException(status_code=404, detail="Exportación no encontrada")
    require_project_permission(db, user.id, row.project_id, REPORTS_EXPORT)
    if row.recipient_user_id != user.id and IDENTITY_USERS_MANAGE not in get_project_permissions(db, user.id, row.project_id)[1]:
        raise HTTPException(status_code=404, detail="Exportación no encontrada")
    return row


@router.get("/{project_id}", response_model=list[SavedExportRead])
def list_exports(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_project_permission(db, user.id, project_id, REPORTS_EXPORT)
    query = db.query(SavedExport).filter(SavedExport.project_id == project_id)
    if IDENTITY_USERS_MANAGE not in get_project_permissions(db, user.id, project_id)[1]:
        query = query.filter(SavedExport.recipient_user_id == user.id)
    return query.order_by(SavedExport.created_at.desc()).all()


@router.post("/{project_id}", response_model=SavedExportRead)
def create_export(project_id: str, payload: SavedExportCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_project_permission(db, user.id, project_id, REPORTS_EXPORT)
    if not db.get(User, payload.recipient_user_id) or not assignment_service.user_has_project_access(db, payload.recipient_user_id, project_id):
        raise HTTPException(status_code=422, detail="El destinatario debe tener acceso al proyecto")
    if REPORTS_EXPORT not in get_project_permissions(db, payload.recipient_user_id, project_id)[1]:
        raise HTTPException(status_code=422, detail="El destinatario necesita permiso para exportar reportes")
    if not payload.template_id and allowed_participant_ids(db, payload.recipient_user_id, project_id) is not None:
        raise HTTPException(status_code=422, detail="El resumen general no admite destinatarios con acceso territorial limitado")
    if payload.template_id:
        template = db.get(BuilderTemplate, payload.template_id)
        if not template or template.project_id != project_id:
            raise HTTPException(status_code=422, detail="Formulario ajeno al proyecto")
    row = SavedExport(project_id=project_id, **payload.model_dump())
    db.add(row)
    db.flush()
    if row.frequency != "manual":
        db.add(ScheduledTask(project_id=project_id, name=f"Exportación: {row.name}", task_type="saved_export",
                             target_id=row.id, frequency=row.frequency))
    db.commit()
    db.refresh(row)
    return row


@router.post("/{export_id}/run")
def run_export(export_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _export(db, user, export_id)
    file = run_saved_export(db, row)
    return {"file_id": file.id, "bytes": len(file.content)}


@router.get("/{export_id}/files")
def list_export_files(export_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _export(db, user, export_id)
    rows = db.query(SavedExportFile.id, SavedExportFile.created_at, func.length(SavedExportFile.content)).filter(SavedExportFile.export_id == export_id).order_by(SavedExportFile.created_at.desc()).limit(20).all()
    return [{"id": row[0], "created_at": row[1], "bytes": row[2]} for row in rows]


@router.get("/{export_id}/files/{file_id}")
def download_export(export_id: str, file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _export(db, user, export_id)
    file = db.query(SavedExportFile).filter(SavedExportFile.id == file_id, SavedExportFile.export_id == row.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if allowed_participant_ids(db, user.id, row.project_id) is not None:
        if not row.template_id or db.query(UserTerritory.id).filter(
            UserTerritory.project_id == row.project_id, UserTerritory.user_id == user.id,
            UserTerritory.created_at > file.created_at,
        ).first():
            raise HTTPException(status_code=403, detail="El alcance territorial cambió; genera una exportación nueva")
    extension = "csv" if row.template_id else "xlsx"
    return Response(content=file.content, media_type=file.media_type,
                    headers={"Content-Disposition": f'attachment; filename="exportacion_{row.id}.{extension}"'})


@router.delete("/{export_id}", status_code=204)
def delete_export(export_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _export(db, user, export_id)
    db.query(ScheduledTask).filter(ScheduledTask.task_type == "saved_export", ScheduledTask.target_id == row.id).delete()
    db.query(SavedExportFile).filter(SavedExportFile.export_id == row.id).delete()
    db.delete(row)
    db.commit()
