"""API de lectura para sistemas externos (bases de datos, BI, paneles de donantes).

Complementa el push saliente de `app.services.integration_service`
(ver docs/86): mientras aquel notifica proactivamente al aprobarse un
registro, esta API deja que el sistema externo consulte cuando quiera,
sin que InfoMatt360 tenga que iniciar nada. Ambas direcciones eran el
alcance real detras de la referencia a "ActivityInfo/TolaData" en la
especificacion original -- no una conexion literal a esas dos plataformas.

No introduce logica de negocio nueva: reutiliza integramente los mismos
servicios que ya usan las pantallas internas
(`runtime_record_service.search_template_records`,
`participant_service.list_participants`, `report_service.project_summary`),
solo agrega una via de acceso autenticada por API key en vez de sesion de
usuario. Reutiliza los mismos permisos del catalogo (`records.read`,
`reports.export`) que ya usan los roles de usuario -- `require_api_key_permission`
verifica el mismo nombre de permiso sobre la lista de la API key.

Conectores BI (docs/96 item #9, docs/114): `/records/tabular`,
`/templates` y `/templates/{id}/schema` sirven de base a los conectores
REST de Power BI y Tableau -- forma plana con columnas estables (derivadas
del esquema del formulario, no de que campos aparecieron en el lote) en vez
de la forma anidada tipo EAV de `/records`, mas un cursor `updated_since`
para refrescos incrementales programados.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.api_key_auth import require_api_key_permission
from app.core.permissions import RECORDS_READ, REPORTS_EXPORT
from app.core.time import to_naive_utc
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.schemas.api_key import ApiKeyAuthContext
from app.schemas.builder import BuilderComponentRead, BuilderTemplateRead
from app.schemas.external_api import ExternalRecordTabularPage
from app.schemas.participants import ParticipantRead
from app.schemas.reports import ReportProjectSummary
from app.schemas.runtime_record import RuntimeRecordPage
from app.services.builder_service import builder_service
from app.services.participant_service import participant_service
from app.services.report_service import report_service
from app.services.runtime_record_service import runtime_record_service

router = APIRouter()


@router.get("/records", response_model=RuntimeRecordPage, summary="Consultar registros de un formulario (por defecto solo aprobados)")
def list_external_records(
    template_id: str = Query(...),
    status_filter: str = Query(default="approved", alias="status"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_READ)),
) -> RuntimeRecordPage:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None or template.project_id != api_key.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key sin acceso a esta plantilla")
    return runtime_record_service.search_template_records(db, template_id, status=status_filter or None, limit=limit, offset=offset)


@router.get("/participants", response_model=list[ParticipantRead], summary="Consultar participantes del proyecto de la API key")
def list_external_participants(
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_READ)),
) -> list[ParticipantRead]:
    return participant_service.list_participants(db, api_key.project_id)


@router.get("/summary", response_model=ReportProjectSummary, summary="Consultar indicadores agregados del proyecto de la API key")
def get_external_summary(
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(REPORTS_EXPORT)),
) -> ReportProjectSummary:
    return report_service.project_summary(db, api_key.project_id)


@router.get("/records/tabular", response_model=ExternalRecordTabularPage, summary="Consultar registros en formato plano/tabular para BI (Power BI, Tableau)")
def list_external_records_tabular(
    template_id: str = Query(...),
    status_filter: str = Query(default="approved", alias="status"),
    updated_since: datetime | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_READ)),
) -> ExternalRecordTabularPage:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None or template.project_id != api_key.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key sin acceso a esta plantilla")
    return runtime_record_service.search_template_records_tabular(
        db, template_id, status=status_filter or None, updated_since=to_naive_utc(updated_since), limit=limit, offset=offset,
    )


@router.get("/templates", response_model=list[BuilderTemplateRead], summary="Listar formularios del proyecto de la API key")
def list_external_templates(
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_READ)),
) -> list[BuilderTemplateRead]:
    return builder_service.list_templates(db, api_key.project_id)


@router.get("/templates/{template_id}/schema", response_model=list[BuilderComponentRead], summary="Consultar el esquema de campos de un formulario")
def get_external_template_schema(
    template_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKeyAuthContext = Depends(require_api_key_permission(RECORDS_READ)),
) -> list[BuilderComponentRead]:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None or template.project_id != api_key.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key sin acceso a esta plantilla")
    return builder_service.list_components(db, template_id)
