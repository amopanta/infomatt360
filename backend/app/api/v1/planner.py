"""Planeador mensual (docs/144): configuración, metas, plan, tablero, cortes y Excel."""

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.models.planner import PlannerCut, PlannerHistory, PlannerPlan, PlannerPopulation, PlannerTarget
from app.services import planner_service as svc
from app.services.assignment_service import assignment_service

router = APIRouter()
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _scope(db: Session, user: User, project_id: str) -> svc.PlannerScope:
    if not assignment_service.user_has_project_access(db, user.id, project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    return svc.planner_scope(db, user.id, project_id)


class SettingsWrite(BaseModel):
    count_policy: str = Field(pattern="^(submitted|approved)$")
    family_key: str = Field(pattern="^(participant|document_id|external_code|field)$")
    family_field: str | None = Field(default=None, max_length=180)
    activity_date_field: str | None = Field(default=None, max_length=180)
    municipality_field: str | None = Field(default=None, max_length=180)
    timezone: str = Field(default="America/Bogota", max_length=60)
    reason: str | None = Field(default=None, max_length=1000)


class TargetWrite(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    municipality: str = Field(default="", max_length=120)
    template_id: str
    gestor_user_id: str | None = None
    unit: str = Field(default="records", pattern="^(records|families)$")
    target: int = Field(ge=0, le=10_000_000)
    reason: str | None = Field(default=None, max_length=1000)


class PopulationWrite(BaseModel):
    year: int = Field(ge=2000, le=2100)
    municipality: str = Field(min_length=1, max_length=120)
    families: int = Field(default=0, ge=0)
    participants: int = Field(default=0, ge=0)
    source: str | None = Field(default=None, max_length=200)
    reason: str | None = Field(default=None, max_length=1000)


class PlanWrite(BaseModel):
    template_id: str
    gestor_user_id: str | None = None
    municipality: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date
    planned_quantity: int = Field(default=0, ge=0)
    planned_participants: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class PlanChange(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    planned_quantity: int | None = Field(default=None, ge=0)
    planned_participants: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3, max_length=1000)


class CutWrite(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


@router.get("/{project_id}/settings")
def read_settings(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    scope = _scope(db, user, project_id)
    return {**svc._settings_dict(svc.get_settings(db, project_id)), "can_manage": scope.can_manage, "supervise": scope.supervise}


@router.put("/{project_id}/settings")
def write_settings(project_id: str, payload: SettingsWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    svc.require_manage(_scope(db, user, project_id))
    return svc._settings_dict(svc.update_settings(db, project_id, user.id, payload.model_dump()))


@router.get("/{project_id}/targets")
def list_targets(project_id: str, year: int = Query(ge=2000, le=2100), month: int | None = Query(default=None, ge=1, le=12),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    scope = _scope(db, user, project_id)
    query = db.query(PlannerTarget).filter(PlannerTarget.project_id == project_id, PlannerTarget.year == year)
    if month:
        query = query.filter(PlannerTarget.month == month)
    return [svc.target_dict(row) for row in query.order_by(PlannerTarget.month, PlannerTarget.municipality).all()
            if (scope.sees_municipality(row.municipality) or not row.municipality) and (scope.supervise or row.gestor_user_id == user.id)]


@router.put("/{project_id}/targets")
def write_target(project_id: str, payload: TargetWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    scope = _scope(db, user, project_id)
    svc.require_manage(scope)
    if payload.municipality and not scope.sees_municipality(payload.municipality):
        raise HTTPException(status_code=403, detail="Municipio fuera de tu territorio autorizado")
    template = db.get(BuilderTemplate, payload.template_id)
    if template is None or template.project_id != project_id:
        raise HTTPException(status_code=422, detail="Formulario no encontrado en el proyecto")
    if payload.month in svc.closed_months(db, project_id, payload.year):
        raise HTTPException(status_code=409, detail="Ese mes tiene un corte cerrado; sus metas no se modifican")
    if payload.gestor_user_id and payload.gestor_user_id not in svc._project_users(db, project_id).values():
        raise HTTPException(status_code=422, detail="El gestor no pertenece al proyecto o está inactivo")
    outcome, row, previous = svc.apply_target(db, project_id, user.id, year=payload.year, month=payload.month, municipality=payload.municipality,
                                              template_id=payload.template_id, gestor_user_id=payload.gestor_user_id, unit=payload.unit,
                                              value=payload.target, mode="replace", reason=payload.reason)
    db.commit()
    return {"outcome": outcome, "previous": previous, "target": svc.target_dict(row)}


@router.get("/targets/template.csv")
def targets_template(user: User = Depends(get_current_user)) -> Response:
    return Response(svc.template_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla_metas.csv"'})


@router.post("/{project_id}/targets/import")
async def import_targets(project_id: str, preview_only: bool = Form(default=True), upload: UploadFile = File(...),
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    scope = _scope(db, user, project_id)
    content = await upload.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera 5 MB")
    return svc.import_targets(db, project_id, scope, upload.filename or "", content, preview_only)


@router.post("/{project_id}/targets/import/errors.csv")
async def import_errors(project_id: str, upload: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    scope = _scope(db, user, project_id)
    result = svc.import_targets(db, project_id, scope, upload.filename or "", await upload.read(MAX_IMPORT_BYTES), True)
    return Response(svc.errors_csv(result), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="errores_metas.csv"'})


@router.get("/{project_id}/population")
def list_population(project_id: str, year: int = Query(ge=2000, le=2100), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    scope = _scope(db, user, project_id)
    rows = db.query(PlannerPopulation).filter(PlannerPopulation.project_id == project_id, PlannerPopulation.year == year).order_by(PlannerPopulation.municipality).all()
    return [{"id": r.id, "year": r.year, "municipality": r.municipality, "families": r.families, "participants": r.participants,
             "source": r.source, "version": r.version} for r in rows if scope.sees_municipality(r.municipality)]


@router.put("/{project_id}/population")
def write_population(project_id: str, payload: PopulationWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = svc.upsert_population(db, project_id, _scope(db, user, project_id), payload.model_dump())
    return {"id": row.id, "year": row.year, "municipality": row.municipality, "families": row.families, "participants": row.participants, "version": row.version}


@router.get("/{project_id}/plans")
def list_plans(project_id: str, year: int = Query(ge=2000, le=2100), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    scope = _scope(db, user, project_id)
    rows = db.query(PlannerPlan).filter(PlannerPlan.project_id == project_id, PlannerPlan.start_date <= date(year, 12, 31),
                                        PlannerPlan.end_date >= date(year, 1, 1)).order_by(PlannerPlan.start_date).all()
    return [svc.plan_dict(r) for r in rows if scope.sees_gestor(r.gestor_user_id) and (not r.municipality or scope.sees_municipality(r.municipality))]


@router.post("/{project_id}/plans", status_code=201)
def create_plan(project_id: str, payload: PlanWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return svc.plan_dict(svc.create_plan(db, project_id, _scope(db, user, project_id), payload.model_dump()))


def _plan(db: Session, user: User, plan_id: str) -> tuple[PlannerPlan, svc.PlannerScope]:
    plan = db.get(PlannerPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Actividad programada no encontrada")
    scope = _scope(db, user, plan.project_id)
    if not scope.sees_gestor(plan.gestor_user_id):
        raise HTTPException(status_code=404, detail="Actividad programada no encontrada")
    return plan, scope


@router.patch("/plans/{plan_id}/reschedule")
def reschedule_plan(plan_id: str, payload: PlanChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    plan, scope = _plan(db, user, plan_id)
    return svc.plan_dict(svc.change_plan(db, scope, plan, payload.model_dump()))


@router.post("/plans/{plan_id}/cancel")
def cancel_plan(plan_id: str, payload: PlanChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    plan, scope = _plan(db, user, plan_id)
    return svc.plan_dict(svc.change_plan(db, scope, plan, payload.model_dump(), cancel=True))


@router.get("/{project_id}/history")
def history(project_id: str, entity_id: str | None = None, limit: int = Query(default=200, ge=1, le=1000),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    svc.require_manage(_scope(db, user, project_id))
    query = db.query(PlannerHistory).filter(PlannerHistory.project_id == project_id)
    if entity_id:
        query = query.filter(PlannerHistory.entity_id == entity_id)
    return [{"id": h.id, "entity_type": h.entity_type, "entity_id": h.entity_id, "previous": h.previous_json, "new": h.new_json,
             "reason": h.reason, "source": h.source, "user_id": h.user_id, "created_at": h.created_at}
            for h in query.order_by(PlannerHistory.created_at.desc()).limit(limit).all()]


def _filters(year: int, month: int | None, municipality: str | None, gestor_user_id: str | None, coordinator_user_id: str | None,
             template_id: str | None) -> svc.Filters:
    return svc.Filters(year=year, month=month, municipality=municipality, gestor_user_id=gestor_user_id,
                       coordinator_user_id=coordinator_user_id, template_id=template_id)


@router.get("/{project_id}/dashboard")
def dashboard(project_id: str, year: int = Query(ge=2000, le=2100), month: int | None = Query(default=None, ge=1, le=12),
              municipality: str | None = None, gestor_user_id: str | None = None, coordinator_user_id: str | None = None,
              template_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    scope = _scope(db, user, project_id)
    return svc.build_report(db, project_id, scope, _filters(year, month, municipality, gestor_user_id, coordinator_user_id, template_id))


@router.get("/{project_id}/export.xlsx")
def export(project_id: str, year: int = Query(ge=2000, le=2100), month: int | None = Query(default=None, ge=1, le=12),
           municipality: str | None = None, gestor_user_id: str | None = None, coordinator_user_id: str | None = None,
           template_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    scope = _scope(db, user, project_id)
    report = svc.build_report(db, project_id, scope, _filters(year, month, municipality, gestor_user_id, coordinator_user_id, template_id))
    name = f"planeador_{year}{'_' + str(month).zfill(2) if month else ''}.xlsx"
    return Response(svc.export_xlsx(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{project_id}/cuts")
def list_cuts(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    _scope(db, user, project_id)
    return [{"id": c.id, "year": c.year, "month": c.month, "closed_by": c.closed_by, "closed_at": c.closed_at}
            for c in db.query(PlannerCut).filter(PlannerCut.project_id == project_id).order_by(PlannerCut.year, PlannerCut.month).all()]


@router.post("/{project_id}/cuts", status_code=201)
def close_cut(project_id: str, payload: CutWrite, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    cut = svc.close_cut(db, project_id, _scope(db, user, project_id), payload.year, payload.month)
    return {"id": cut.id, "year": cut.year, "month": cut.month, "closed_at": cut.closed_at}


@router.get("/{project_id}/catalog")
def catalog(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Actividades (formularios) y personas que el usuario puede ver en el planeador."""
    scope = _scope(db, user, project_id)
    templates = db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id, BuilderTemplate.status != "archived").order_by(BuilderTemplate.name).all()
    if scope.supervise:
        ids = set(svc._project_users(db, project_id).values())
        people = db.query(User).filter(User.id.in_(ids)).order_by(User.full_name).all() if ids else []
    else:
        people = [user]
    return {"activities": [{"id": t.id, "name": t.name, "status": t.status} for t in templates],
            "people": [{"id": p.id, "full_name": p.full_name, "email": p.email} for p in people],
            "can_manage": scope.can_manage, "supervise": scope.supervise}
