from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.identity import User
from app.models.builder import BuilderTemplate
from app.models.reports import Report, ReportIndicator
from app.schemas.form_report import FormReportRead
from app.schemas.report_catalog import CatalogReportConfig, CatalogReportRead, CatalogReportResult, LibraryIndicatorCreate, LibraryIndicatorRead, ReportShareIssued, ReportShareRead, ReportShareRequest
from app.services.assignment_service import assignment_service
from app.services.report_catalog_service import report_catalog_service as catalog
from app.services.form_report_service import form_report_service
from app.services.indicator_library_service import indicator_library_service as indicator_library


router = APIRouter()


@router.get("/indicators/project/{project_id}", response_model=list[LibraryIndicatorRead])
def list_indicators(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[LibraryIndicatorRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    rows = db.query(ReportIndicator).filter(ReportIndicator.project_id == project_id).order_by(ReportIndicator.code).all()
    return [indicator_library.read(row) for row in rows]


@router.post("/indicators", response_model=LibraryIndicatorRead)
def create_indicator(payload: LibraryIndicatorCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> LibraryIndicatorRead:
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return indicator_library.save(db, payload.project_id, payload.definition)


@router.put("/indicators/{indicator_id}", response_model=LibraryIndicatorRead)
def update_indicator(indicator_id: str, payload: LibraryIndicatorCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> LibraryIndicatorRead:
    require_project_permission(db, current_user.id, payload.project_id, BUILDER_WRITE)
    return indicator_library.save(db, payload.project_id, payload.definition, indicator_id)


@router.get("/indicators-template")
def download_indicator_template(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    return Response(content=indicator_library.template(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="plantilla_indicadores.xlsx"'})


@router.post("/indicators-import/preview")
async def preview_indicator_import(project_id: str = Form(...), upload: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = await upload.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(status_code=413, detail="El Excel supera 10 MB")
    definitions, errors = indicator_library.parse(db, project_id, content)
    return {"indicators": [item.model_dump() for item in definitions], "errors": errors}


@router.post("/indicators-import/apply", response_model=list[LibraryIndicatorRead])
async def apply_indicator_import(project_id: str = Form(...), upload: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[LibraryIndicatorRead]:
    require_project_permission(db, current_user.id, project_id, BUILDER_WRITE)
    content = await upload.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(status_code=413, detail="El Excel supera 10 MB")
    return indicator_library.import_rows(db, project_id, content)


@router.get("/forms/{template_id}", response_model=FormReportRead)
def individual_form_report(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FormReportRead:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, template.project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    return form_report_service.resolve(db, template)


@router.get("/shared/{token}", response_model=CatalogReportResult)
def public_report(token: str, db: Session = Depends(get_db)) -> CatalogReportResult:
    return catalog.public_report(db, token)


@router.get("/catalog/project/{project_id}", response_model=list[CatalogReportRead])
def list_catalog(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[CatalogReportRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    rows = db.query(Report).filter(Report.project_id == project_id, Report.report_type == "indicator_board").order_by(Report.created_at.desc()).all()
    return [catalog.read(row) for row in rows]


@router.post("/catalog", response_model=CatalogReportRead)
def create_catalog(config: CatalogReportConfig, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CatalogReportRead:
    require_project_permission(db, current_user.id, config.project_id, BUILDER_WRITE)
    return catalog.create(db, config)


@router.get("/catalog/{report_id}", response_model=CatalogReportResult)
def get_catalog(report_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CatalogReportResult:
    row = catalog.get(db, report_id)
    if not assignment_service.user_has_project_access(db, current_user.id, row.project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    return catalog.resolve(db, row)


@router.put("/catalog/{report_id}", response_model=CatalogReportRead)
def update_catalog(report_id: str, config: CatalogReportConfig, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CatalogReportRead:
    row = catalog.get(db, report_id)
    require_project_permission(db, current_user.id, row.project_id, BUILDER_WRITE)
    return catalog.update(db, row, config)


@router.get("/catalog/{report_id}/links", response_model=list[ReportShareRead])
def list_catalog_links(report_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ReportShareRead]:
    row = catalog.get(db, report_id)
    require_project_permission(db, current_user.id, row.project_id, BUILDER_WRITE)
    return catalog.links(db, row.id)


@router.post("/catalog/{report_id}/links", response_model=ReportShareIssued)
def share_catalog(report_id: str, payload: ReportShareRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportShareIssued:
    row = catalog.get(db, report_id)
    require_project_permission(db, current_user.id, row.project_id, BUILDER_WRITE)
    return catalog.issue_link(db, row, payload.expires_at)


@router.post("/catalog/{report_id}/links/{link_id}/revoke", response_model=ReportShareRead)
def revoke_catalog_link(report_id: str, link_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReportShareRead:
    row = catalog.get(db, report_id)
    require_project_permission(db, current_user.id, row.project_id, BUILDER_WRITE)
    return catalog.revoke(db, row.id, link_id)
