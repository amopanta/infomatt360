from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.files import FileAsset
from app.models.identity import User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.files import EvidenceBatchDownloadRequest, FileAssetCreate, FileAssetRead
from app.services.assignment_service import assignment_service
from app.services.file_service import file_service

router = APIRouter()
UPLOAD_ASSET_TYPES = {"FILE", "PDF", "MULTIFILE", "IMAGE", "AUDIO", "VIDEO", "SIGNATURE"}


def validate_asset_relations(db: Session, project_id: str, participant_id: str | None, record_id: str | None) -> None:
    if participant_id and not db.query(Participant).filter(Participant.id == participant_id, Participant.project_id == project_id).first():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El participante no pertenece al proyecto")
    if record_id and not db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id, RuntimeRecord.project_id == project_id).first():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El registro no pertenece al proyecto")


@router.post("/", response_model=FileAssetRead)
def create_file_asset(payload: FileAssetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileAssetRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    validate_asset_relations(db, payload.project_id, payload.participant_id, payload.record_id)
    return file_service.create_asset(db, payload, current_user.id)


@router.post("/upload", response_model=FileAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_file_asset(
    project_id: str = Form(...),
    asset_type: str = Form(...),
    participant_id: str | None = Form(None),
    record_id: str | None = Form(None),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileAssetRead:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    if asset_type.upper() not in UPLOAD_ASSET_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tipo de evidencia no soportado")
    validate_asset_relations(db, project_id, participant_id, record_id)
    try:
        return await file_service.upload(
            db,
            project_id=project_id,
            asset_type=asset_type,
            upload=upload,
            user_id=current_user.id,
            participant_id=participant_id,
            record_id=record_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc


@router.get("/project/{project_id}", response_model=list[FileAssetRead])
def list_project_files(
    project_id: str,
    participant_id: str | None = None,
    record_id: str | None = None,
    template_id: str | None = None,
    status_filter: str | None = None,
    created_by: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FileAssetRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return file_service.list_assets(
        db,
        project_id,
        participant_id,
        record_id,
        template_id=template_id,
        status=status_filter,
        created_by=created_by,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{file_id}/download", summary="Descargar una evidencia")
def download_file_asset(file_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    asset = db.query(FileAsset).filter(FileAsset.id == file_id).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidencia no encontrada")
    if not assignment_service.user_has_project_access(db, current_user.id, asset.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    content = file_service.read_asset_bytes(db, asset)
    safe_name = "".join(character if character.isascii() and (character.isalnum() or character in "-_.") else "_" for character in asset.original_name).strip("_") or "evidencia"
    return Response(
        content=content,
        media_type=asset.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/project/{project_id}/download-batch", summary="Descargar evidencias en lote (ZIP)")
def download_file_assets_batch(project_id: str, payload: EvidenceBatchDownloadRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")

    if payload.asset_ids:
        asset_ids = payload.asset_ids
    else:
        asset_ids = file_service.list_filtered_asset_ids(
            db,
            project_id,
            participant_id=payload.participant_id,
            template_id=payload.template_id,
            status=payload.status,
            created_by=payload.created_by,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
    if not asset_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No hay evidencias que coincidan con la seleccion")
    if len(asset_ids) > settings.evidence_batch_max_records:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"El lote excede el maximo permitido ({settings.evidence_batch_max_records} archivos); reduce la seleccion o el filtro.")

    total_bytes = db.query(func.sum(FileAsset.size_bytes)).filter(FileAsset.id.in_(asset_ids)).scalar() or 0
    max_bytes = settings.evidence_batch_max_total_size_mb * 1024 * 1024
    if total_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"El lote pesa {total_bytes // (1024 * 1024)} MB y excede el maximo permitido ({settings.evidence_batch_max_total_size_mb} MB); reduce la seleccion o el filtro.",
        )

    zip_bytes = file_service.download_batch(db, project_id, asset_ids)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="evidencias-lote.zip"'},
    )


@router.get("/project/{project_id}/uploaders", summary="Listar gestores que subieron evidencias")
def list_project_uploaders(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return file_service.list_uploaders(db, project_id)
