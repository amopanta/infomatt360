"""Monitoreo de equipos de campo y recorrido de gestores.

- POST /field-devices/heartbeat: la app informa su estado (registros sin
  enviar, última sincronización, errores) y los puntos del recorrido.
- GET /field-devices/project/{id}/status: tablero del supervisor.
- GET /field-devices/project/{id}/routes: recorrido por gestor y periodo.

El recorrido solo lo ven supervisión y administración (revisar, coordinar o
gestionar usuarios del proyecto); el gestor no consulta el de otros.
"""

import json
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE, RECORDS_COORDINATE, RECORDS_REVIEW
from app.core.time import to_naive_utc, utc_now
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.device_status import FieldDeviceStatus, FieldRoutePoint
from app.models.identity import User
from app.services.assignment_service import assignment_service

router = APIRouter()

SUPERVISION_PERMISSIONS = {RECORDS_REVIEW, RECORDS_COORDINATE, IDENTITY_USERS_MANAGE}
# Sin latido en este tiempo el equipo se marca "sin conexión reciente".
STALE_AFTER = timedelta(hours=24)
# Registros sin enviar por más de este tiempo se señalan como atrasados.
PENDING_DELAYED_AFTER = timedelta(hours=24)
HEARTBEAT_INTERVAL_SECONDS = 300
ROUTE_INTERVAL_SECONDS = 120


class RoutePointIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    recorded_at: datetime


class DeviceErrorIn(BaseModel):
    at: datetime | None = None
    message: str = Field(max_length=500)


class HeartbeatIn(BaseModel):
    device_id: str = Field(min_length=4, max_length=120)
    project_id: str | None = None
    device_name: str = Field(default="", max_length=200)
    platform: str = Field(default="", max_length=60)
    app_version: str = Field(default="", max_length=30)
    pending_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)
    draft_count: int = Field(default=0, ge=0)
    pending_evidence_count: int = Field(default=0, ge=0)
    oldest_pending_at: datetime | None = None
    last_sync_at: datetime | None = None
    recent_errors: list[DeviceErrorIn] = Field(default_factory=list, max_length=20)
    route_points: list[RoutePointIn] = Field(default_factory=list, max_length=1000)


class HeartbeatOut(BaseModel):
    received_points: int
    # El administrador pidió borrar los datos de este usuario en el equipo
    wipe_requested: bool = False
    heartbeat_interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS
    route_interval_seconds: int = ROUTE_INTERVAL_SECONDS


class DeviceStatusOut(BaseModel):
    device_id: str
    user_id: str
    user_name: str
    user_email: str
    device_name: str
    platform: str
    app_version: str
    pending_count: int
    error_count: int
    conflict_count: int
    draft_count: int
    pending_evidence_count: int
    oldest_pending_at: datetime | None
    last_sync_at: datetime | None
    last_seen_at: datetime
    last_error: str | None
    recent_errors: list[dict]
    last_latitude: float | None
    last_longitude: float | None
    last_location_at: datetime | None
    level: str
    alerts: list[str]
    wipe_requested_at: datetime | None = None
    wipe_completed_at: datetime | None = None


class RoutePointOut(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: float | None
    recorded_at: datetime


class RouteSummaryOut(BaseModel):
    user_id: str
    user_name: str
    point_count: int
    distance_km: float
    first_at: datetime | None
    last_at: datetime | None
    points: list[RoutePointOut] = []


def _health(row: FieldDeviceStatus, now: datetime) -> tuple[str, list[str]]:
    alerts: list[str] = []
    level = "ok"
    if row.error_count or row.conflict_count:
        level = "danger"
        if row.error_count:
            alerts.append(f"{row.error_count} registro(s) con error")
        if row.conflict_count:
            alerts.append(f"{row.conflict_count} registro(s) en conflicto")
    if row.pending_count or row.pending_evidence_count:
        delayed = row.oldest_pending_at is not None and now - row.oldest_pending_at > PENDING_DELAYED_AFTER
        if delayed:
            level = "danger"
            alerts.append(f"{row.pending_count} registro(s) sin enviar hace más de un día")
        else:
            level = "warning" if level == "ok" else level
            if row.pending_count:
                alerts.append(f"{row.pending_count} registro(s) sin enviar")
            if row.pending_evidence_count:
                alerts.append(f"{row.pending_evidence_count} archivo(s) sin subir")
    if now - row.last_seen_at > STALE_AFTER:
        level = "danger" if row.pending_count else ("warning" if level == "ok" else level)
        alerts.append("Sin conexión con el servidor hace más de un día")
    return level, alerts


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def route_distance_km(points: list[FieldRoutePoint]) -> float:
    total = 0.0
    for prev, cur in zip(points, points[1:]):
        # Saltos con mala precisión (>100 m) inflan la distancia: se omiten.
        if (cur.accuracy_m or 0) > 100 or (prev.accuracy_m or 0) > 100:
            continue
        total += haversine_km((prev.latitude, prev.longitude), (cur.latitude, cur.longitude))
    return round(total, 2)


@router.post("/heartbeat", response_model=HeartbeatOut)
def heartbeat(payload: HeartbeatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.project_id and not assignment_service.user_has_project_access(db, user.id, payload.project_id):
        raise HTTPException(status_code=403, detail="Sin acceso al proyecto")
    now = utc_now()
    row = (
        db.query(FieldDeviceStatus)
        .filter(FieldDeviceStatus.device_id == payload.device_id, FieldDeviceStatus.user_id == user.id)
        .first()
    )
    if row is None:
        row = FieldDeviceStatus(device_id=payload.device_id, user_id=user.id, created_at=now)
        db.add(row)
    row.project_id = payload.project_id or row.project_id
    row.device_name = payload.device_name.strip()
    row.platform = payload.platform.strip()
    row.app_version = payload.app_version.strip()
    row.pending_count = payload.pending_count
    row.error_count = payload.error_count
    row.conflict_count = payload.conflict_count
    row.draft_count = payload.draft_count
    row.pending_evidence_count = payload.pending_evidence_count
    row.oldest_pending_at = to_naive_utc(payload.oldest_pending_at)
    row.last_sync_at = to_naive_utc(payload.last_sync_at) or row.last_sync_at
    errors = [{"at": to_naive_utc(e.at).isoformat() if e.at else None, "message": e.message.strip()} for e in payload.recent_errors]
    row.recent_errors_json = json.dumps(errors, ensure_ascii=False)
    row.last_error = errors[0]["message"] if errors else None
    row.last_seen_at = now

    # Puntos del recorrido: un reenvío (respuesta perdida) no los duplica.
    received = 0
    if payload.route_points:
        incoming = sorted(payload.route_points, key=lambda p: p.recorded_at)
        times = [to_naive_utc(p.recorded_at) for p in incoming]
        existing = {
            value
            for (value,) in db.query(FieldRoutePoint.recorded_at).filter(
                FieldRoutePoint.device_id == payload.device_id,
                FieldRoutePoint.user_id == user.id,
                FieldRoutePoint.recorded_at.in_(times),
            )
        }
        for point, recorded_at in zip(incoming, times):
            if recorded_at in existing:
                continue
            existing.add(recorded_at)
            db.add(FieldRoutePoint(
                device_id=payload.device_id,
                user_id=user.id,
                project_id=payload.project_id,
                latitude=point.latitude,
                longitude=point.longitude,
                accuracy_m=point.accuracy_m,
                recorded_at=recorded_at,
                received_at=now,
            ))
            received += 1
        last = incoming[-1]
        last_at = times[-1]
        if row.last_location_at is None or last_at >= row.last_location_at:
            row.last_latitude, row.last_longitude, row.last_location_at = last.latitude, last.longitude, last_at
    try:
        db.commit()
    except IntegrityError:
        # Dos latidos simultáneos del mismo equipo: el otro ya guardó.
        db.rollback()
        raise HTTPException(status_code=409, detail="Latido duplicado, reintente")
    return HeartbeatOut(received_points=received, wipe_requested=row.wipe_requested_at is not None and row.wipe_completed_at is None)


@router.get("/project/{project_id}/status", response_model=list[DeviceStatusOut])
def project_device_status(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_any_project_permission(db, user.id, project_id, SUPERVISION_PERMISSIONS)
    rows = (
        db.query(FieldDeviceStatus, User)
        .join(User, User.id == FieldDeviceStatus.user_id)
        .filter(FieldDeviceStatus.project_id == project_id)
        .all()
    )
    now = utc_now()
    result: list[DeviceStatusOut] = []
    for row, owner in rows:
        level, alerts = _health(row, now)
        try:
            recent = json.loads(row.recent_errors_json or "[]")
        except ValueError:
            recent = []
        result.append(DeviceStatusOut(
            device_id=row.device_id, user_id=row.user_id, user_name=owner.full_name, user_email=owner.email,
            device_name=row.device_name, platform=row.platform, app_version=row.app_version,
            pending_count=row.pending_count, error_count=row.error_count, conflict_count=row.conflict_count,
            draft_count=row.draft_count, pending_evidence_count=row.pending_evidence_count,
            oldest_pending_at=row.oldest_pending_at, last_sync_at=row.last_sync_at, last_seen_at=row.last_seen_at,
            last_error=row.last_error, recent_errors=recent if isinstance(recent, list) else [],
            last_latitude=row.last_latitude, last_longitude=row.last_longitude, last_location_at=row.last_location_at,
            level=level, alerts=alerts,
            wipe_requested_at=row.wipe_requested_at, wipe_completed_at=row.wipe_completed_at,
        ))
    order = {"danger": 0, "warning": 1, "ok": 2}
    result.sort(key=lambda item: (order[item.level], -item.pending_count, item.user_name.lower()))
    return result


@router.get("/project/{project_id}/routes", response_model=list[RouteSummaryOut])
def project_routes(
    project_id: str,
    date_from: datetime = Query(..., description="Inicio del periodo (p. ej. inicio del día local)"),
    date_to: datetime = Query(...),
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_any_project_permission(db, user.id, project_id, SUPERVISION_PERMISSIONS)
    start, end = to_naive_utc(date_from), to_naive_utc(date_to)
    if end <= start or end - start > timedelta(days=31):
        raise HTTPException(status_code=422, detail="El periodo debe ser de máximo 31 días")
    query = db.query(FieldRoutePoint).filter(
        FieldRoutePoint.project_id == project_id,
        FieldRoutePoint.recorded_at >= start,
        FieldRoutePoint.recorded_at < end,
    )
    if user_id:
        query = query.filter(FieldRoutePoint.user_id == user_id)
    by_user: dict[str, list[FieldRoutePoint]] = {}
    for point in query.order_by(FieldRoutePoint.user_id, FieldRoutePoint.recorded_at).all():
        by_user.setdefault(point.user_id, []).append(point)
    names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(list(by_user))).all()} if by_user else {}
    summaries = [
        RouteSummaryOut(
            user_id=uid,
            user_name=names.get(uid, uid),
            point_count=len(points),
            distance_km=route_distance_km(points),
            first_at=points[0].recorded_at,
            last_at=points[-1].recorded_at,
            # Sin user_id es el resumen del equipo; los puntos van al pedir un gestor.
            points=[RoutePointOut(latitude=p.latitude, longitude=p.longitude, accuracy_m=p.accuracy_m, recorded_at=p.recorded_at) for p in points] if user_id else [],
        )
        for uid, points in by_user.items()
    ]
    summaries.sort(key=lambda s: s.user_name.lower())
    return summaries


class WipeRequest(BaseModel):
    device_id: str = Field(min_length=4, max_length=120)
    user_id: str = Field(min_length=1, max_length=36)


class WipeAck(BaseModel):
    device_id: str = Field(min_length=4, max_length=120)


@router.post("/project/{project_id}/wipe", response_model=DeviceStatusOut)
def request_remote_wipe(project_id: str, payload: WipeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Pide borrar los datos de un usuario en un equipo (tablet perdida o
    reasignada). Solo administración del proyecto. El equipo intenta enviar
    lo pendiente antes de borrar."""
    require_any_project_permission(db, user.id, project_id, {IDENTITY_USERS_MANAGE})
    row = (
        db.query(FieldDeviceStatus)
        .filter(FieldDeviceStatus.project_id == project_id, FieldDeviceStatus.device_id == payload.device_id,
                FieldDeviceStatus.user_id == payload.user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado en el proyecto")
    row.wipe_requested_at = utc_now()
    row.wipe_requested_by = user.id
    row.wipe_completed_at = None
    db.add(AuditLog(project_id=project_id, user_id=user.id, module="field_devices", action="remote_wipe_requested",
                    entity_type="field_device", entity_id=row.device_id[:80],
                    after_json=json.dumps({"device_id": row.device_id, "user_id": row.user_id})))
    db.commit()
    return next(item for item in project_device_status(project_id, db, user) if item.device_id == row.device_id and item.user_id == row.user_id)


@router.post("/wipe-ack")
def acknowledge_remote_wipe(payload: WipeAck, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, bool]:
    """El equipo confirma que borró los datos del usuario."""
    row = db.query(FieldDeviceStatus).filter(FieldDeviceStatus.device_id == payload.device_id, FieldDeviceStatus.user_id == user.id).first()
    if row is None or row.wipe_requested_at is None:
        raise HTTPException(status_code=404, detail="No hay borrado pendiente para este equipo")
    row.wipe_completed_at = utc_now()
    row.pending_count = row.error_count = row.conflict_count = row.draft_count = row.pending_evidence_count = 0
    row.oldest_pending_at = None
    db.add(AuditLog(project_id=row.project_id, user_id=user.id, module="field_devices", action="remote_wipe_completed",
                    entity_type="field_device", entity_id=row.device_id[:80]))
    db.commit()
    return {"wiped": True}

