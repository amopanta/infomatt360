"""Planeador mensual (docs/144): metas, ejecución válida, cumplimiento y Excel.

Lo ejecutado se calcula desde `runtime_records` con las reglas del
proyecto (`PlannerSettings`): qué estados cuentan, cuál es la llave de
familia, qué campo trae la fecha y el municipio. Un mes con corte cerrado
se lee de su foto (`PlannerCut`) y no cambia aunque cambien metas o
registros.

Hechos y metas se agrupan por (mes, municipio, actividad, gestor). La
actividad es el formulario. Cumplimiento = ejecutado / meta × 100 cuando la
meta es mayor que cero; con meta cero se muestra «Sin meta». Los totales se
ponderan (suma de ejecutados / suma de metas), nunca promediando porcentajes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.orm import Session

from app.api.permissions import get_project_permissions
from app.core.permissions import (
    IDENTITY_USERS_MANAGE,
    PLANNER_MANAGE,
    RECORDS_APPROVE,
    RECORDS_COORDINATE,
    RECORDS_REVIEW,
    RECORDS_WRITE,
    REPORTS_EXPORT,
)
from app.core.time import utc_now
from app.models.builder import BuilderTemplate
from app.models.case_management import UserTerritory
from app.models.gestor_team import GestorTeam, GestorTeamUser
from app.models.identity import User
from app.models.participants import Participant
from app.models.planner import PlannerCut, PlannerHistory, PlannerPlan, PlannerPopulation, PlannerSettings, PlannerTarget
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue

MANAGE_PERMISSIONS = {PLANNER_MANAGE, IDENTITY_USERS_MANAGE}
SUPERVISE_PERMISSIONS = MANAGE_PERMISSIONS | {RECORDS_REVIEW, RECORDS_APPROVE, RECORDS_COORDINATE, REPORTS_EXPORT}

# "Lo que llega": todo lo enviado que no se anuló ni se rechazó.
SUBMITTED_STATUSES = {"submitted", "under_review", "tech_approved", "coordinator_approved", "returned", "corrected", "approved", "synced"}
APPROVED_STATUSES = {"approved", "synced"}
COUNT_POLICIES = {"submitted", "approved"}
FAMILY_KEYS = {"participant", "document_id", "external_code", "field"}
UNITS = {"records", "families"}
UNIT_LABELS = {"records": "Actividades", "families": "Familias únicas"}
IMPORT_MODES = {"crear": "create", "create": "create", "reemplazar": "replace", "replace": "replace", "sumar": "add", "add": "add"}


# Zonas sin horario de verano: sirven aunque el sistema no traiga la base
# de zonas horarias (Windows sin el paquete tzdata).
FIXED_ZONES = {"America/Bogota": -5, "America/Lima": -5, "America/Panama": -5, "America/Guayaquil": -5,
               "America/Caracas": -4, "America/La_Paz": -4, "UTC": 0}


def resolve_timezone(name: str | None) -> tzinfo:
    name = name or "America/Bogota"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        if name in FIXED_ZONES:
            return timezone(timedelta(hours=FIXED_ZONES[name]), name)
        raise


def norm(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def compliance(executed: int, target: int) -> float | None:
    """None significa «Sin meta». No se trunca por encima de 100 %."""
    return round(executed / target * 100, 2) if target > 0 else None


# ── Alcance por perfil ─────────────────────────────────────────────────────


@dataclass
class PlannerScope:
    user_id: str
    can_manage: bool
    supervise: bool
    municipalities: set[str] | None  # None: sin restricción territorial
    departments_only: set[str] = field(default_factory=set)

    def sees_gestor(self, gestor_user_id: str | None) -> bool:
        return self.supervise or gestor_user_id == self.user_id

    def sees_municipality(self, municipality: str) -> bool:
        return self.municipalities is None or norm(municipality) in self.municipalities


def planner_scope(db: Session, user_id: str, project_id: str) -> PlannerScope:
    _, permissions = get_project_permissions(db, user_id, project_id)
    supervise = bool(permissions & SUPERVISE_PERMISSIONS)
    if not supervise and RECORDS_WRITE not in permissions:
        raise HTTPException(status_code=403, detail="Sin acceso al planeador de este proyecto")
    municipalities: set[str] | None = None
    if IDENTITY_USERS_MANAGE not in permissions:
        territories = db.query(UserTerritory).filter(UserTerritory.user_id == user_id, UserTerritory.project_id == project_id).all()
        if territories:
            # Un territorio sin municipio cubre todo el departamento: se resuelve con los municipios conocidos.
            municipalities = {norm(t.municipality) for t in territories if t.municipality}
            whole = {norm(t.department) for t in territories if not t.municipality}
            if whole:
                for participant in db.query(Participant.metadata_json).filter(Participant.project_id == project_id).all():
                    meta = _metadata(participant[0])
                    if norm(meta.get("department") or meta.get("departamento")) in whole:
                        municipalities.add(norm(meta.get("municipality") or meta.get("municipio")))
    return PlannerScope(user_id=user_id, can_manage=bool(permissions & MANAGE_PERMISSIONS), supervise=supervise, municipalities=municipalities)


def require_manage(scope: PlannerScope) -> None:
    if not scope.can_manage:
        raise HTTPException(status_code=403, detail="Se requiere el permiso planner.manage")


# ── Configuración ──────────────────────────────────────────────────────────


def get_settings(db: Session, project_id: str) -> PlannerSettings:
    row = db.get(PlannerSettings, project_id)
    return row or PlannerSettings(project_id=project_id, count_policy="approved", family_key="participant", timezone="America/Bogota")


def update_settings(db: Session, project_id: str, user_id: str, data: dict) -> PlannerSettings:
    if data.get("count_policy") not in COUNT_POLICIES:
        raise HTTPException(status_code=422, detail="La regla de conteo debe ser 'submitted' (lo que llega) o 'approved' (solo aprobado)")
    if data.get("family_key") not in FAMILY_KEYS:
        raise HTTPException(status_code=422, detail="Llave de familia no válida")
    if data["family_key"] == "field" and not (data.get("family_field") or "").strip():
        raise HTTPException(status_code=422, detail="Indica el campo del formulario que identifica la familia")
    try:
        resolve_timezone(data.get("timezone"))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Zona horaria no válida") from exc
    row = db.get(PlannerSettings, project_id)
    previous = _settings_dict(row) if row else None
    if row is None:
        row = PlannerSettings(project_id=project_id)
        db.add(row)
    row.count_policy = data["count_policy"]
    row.family_key = data["family_key"]
    row.family_field = (data.get("family_field") or "").strip() or None
    row.activity_date_field = (data.get("activity_date_field") or "").strip() or None
    row.municipality_field = (data.get("municipality_field") or "").strip() or None
    row.timezone = data.get("timezone") or "America/Bogota"
    row.updated_by = user_id
    row.updated_at = utc_now()
    _history(db, project_id, "settings", project_id, previous, _settings_dict(row), data.get("reason"), user_id)
    db.commit()
    return row


def _settings_dict(row: PlannerSettings) -> dict:
    return {"count_policy": row.count_policy, "family_key": row.family_key, "family_field": row.family_field,
            "activity_date_field": row.activity_date_field, "municipality_field": row.municipality_field, "timezone": row.timezone}


def _history(db: Session, project_id: str, entity_type: str, entity_id: str, previous: dict | None, new: dict,
             reason: str | None, user_id: str, source: str = "manual", client_ref: str | None = None) -> None:
    db.add(PlannerHistory(project_id=project_id, entity_type=entity_type, entity_id=entity_id,
                          previous_json=json.dumps(previous, ensure_ascii=False, default=str) if previous is not None else None,
                          new_json=json.dumps(new, ensure_ascii=False, default=str), reason=(reason or "").strip() or None,
                          source=source, client_ref=client_ref, user_id=user_id))


# ── Equipos y territorio ──────────────────────────────────────────────────


def _metadata(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def coordinator_by_gestor(db: Session, project_id: str) -> dict[str, str | None]:
    """Coordinador heredado: el responsable del primer equipo (por nombre) del gestor."""
    rows = db.query(GestorTeamUser.user_id, GestorTeam.coordinator_user_id).join(GestorTeam, GestorTeam.id == GestorTeamUser.team_id).filter(
        GestorTeam.project_id == project_id).order_by(GestorTeam.name).all()
    result: dict[str, str | None] = {}
    for user_id, coordinator in rows:
        if result.get(user_id) is None:
            result[user_id] = coordinator
    return result


def gestor_municipality(db: Session, project_id: str, user_id: str) -> str:
    """Municipio heredado de la asignación territorial vigente si es único; si
    no, el municipio del perfil del usuario (docs/145)."""
    rows = {t.municipality.strip() for t in db.query(UserTerritory).filter(UserTerritory.project_id == project_id, UserTerritory.user_id == user_id).all() if t.municipality}
    if len(rows) == 1:
        return rows.pop()
    user = db.get(User, user_id)
    return (user.municipality or "").strip() if user and not rows else ""


# ── Hechos: ejecución válida ──────────────────────────────────────────────


@dataclass
class Fact:
    month: int
    municipality: str
    template_id: str
    gestor_user_id: str | None
    coordinator_user_id: str | None
    records: int = 0
    families: set[str] = field(default_factory=set)


def _parse_date(raw: object) -> date | None:
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def compute_facts(db: Session, project_id: str, year: int, settings: PlannerSettings) -> list[Fact]:
    statuses = APPROVED_STATUSES if settings.count_policy == "approved" else SUBMITTED_STATUSES
    template_ids = {row[0] for row in db.query(BuilderTemplate.id).filter(BuilderTemplate.project_id == project_id).all()}
    if not template_ids:
        return []
    records = db.query(RuntimeRecord).filter(
        RuntimeRecord.project_id == project_id, RuntimeRecord.template_id.in_(template_ids),
        RuntimeRecord.status.in_(statuses), RuntimeRecord.parent_record_id.is_(None),
    ).all()
    wanted_fields = {name for name in (settings.activity_date_field, settings.municipality_field,
                                       settings.family_field if settings.family_key == "field" else None) if name}
    values: dict[str, dict[str, object]] = defaultdict(dict)
    if wanted_fields and records:
        ids = [record.id for record in records]
        for start in range(0, len(ids), 500):
            for value in db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id.in_(ids[start:start + 500]),
                                                             RuntimeRecordValue.field_name.in_(wanted_fields)).all():
                try:
                    values[value.record_id][value.field_name] = json.loads(value.field_value_json)
                except ValueError:
                    values[value.record_id][value.field_name] = value.field_value_json
    participants = {p.id: p for p in db.query(Participant).filter(Participant.id.in_({r.participant_id for r in records if r.participant_id})).all()} if records else {}
    coordinators = coordinator_by_gestor(db, project_id)
    gestor_town: dict[str, str] = {}
    tz = resolve_timezone(settings.timezone)
    facts: dict[tuple, Fact] = {}
    for record in records:
        own = values.get(record.id, {})
        activity_day = _parse_date(own.get(settings.activity_date_field)) if settings.activity_date_field else None
        if activity_day is None:
            activity_day = record.created_at.replace(tzinfo=timezone.utc).astimezone(tz).date()
        if activity_day.year != year:
            continue
        participant = participants.get(record.participant_id or "")
        meta = _metadata(participant.metadata_json) if participant else {}
        municipality = str(meta.get("municipality") or meta.get("municipio") or "").strip()
        if not municipality and settings.municipality_field:
            municipality = str(own.get(settings.municipality_field) or "").strip()
        if not municipality and record.captured_by_municipality:
            municipality = record.captured_by_municipality.strip()
        if not municipality and record.submitted_by:
            if record.submitted_by not in gestor_town:
                gestor_town[record.submitted_by] = gestor_municipality(db, project_id, record.submitted_by)
            municipality = gestor_town[record.submitted_by]
        family = _family_key(settings, record, participant, own)
        key = (activity_day.month, norm(municipality), record.template_id, record.submitted_by)
        fact = facts.get(key)
        if fact is None:
            fact = facts[key] = Fact(activity_day.month, municipality, record.template_id, record.submitted_by,
                                     coordinators.get(record.submitted_by or ""))
        fact.records += 1
        if family:
            fact.families.add(family)
    return list(facts.values())


def _family_key(settings: PlannerSettings, record: RuntimeRecord, participant: Participant | None, own: dict) -> str | None:
    if settings.family_key == "participant":
        return record.participant_id
    if settings.family_key == "document_id":
        return norm(participant.document_id) or None if participant else None
    if settings.family_key == "external_code":
        return norm(participant.external_code) or None if participant else None
    raw = own.get(settings.family_field or "")
    return norm(str(raw)) or None if raw not in (None, "") else None


# ── Metas ─────────────────────────────────────────────────────────────────


def scope_key(year: int, month: int, municipality: str, template_id: str, gestor_user_id: str | None, unit: str) -> str:
    raw = "|".join([str(year), str(month), norm(municipality), template_id, gestor_user_id or "", unit])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def target_dict(row: PlannerTarget) -> dict:
    return {"id": row.id, "year": row.year, "month": row.month, "municipality": row.municipality, "template_id": row.template_id,
            "gestor_user_id": row.gestor_user_id, "unit": row.unit, "target": row.target, "version": row.version}


def closed_months(db: Session, project_id: str, year: int) -> set[int]:
    return {row[0] for row in db.query(PlannerCut.month).filter(PlannerCut.project_id == project_id, PlannerCut.year == year).all()}


def apply_target(db: Session, project_id: str, user_id: str, *, year: int, month: int, municipality: str, template_id: str,
                 gestor_user_id: str | None, unit: str, value: int, mode: str, reason: str | None,
                 source: str = "manual", client_ref: str | None = None) -> tuple[str, PlannerTarget | None, int | None]:
    """Crea, reemplaza o suma una meta. Devuelve (resultado, fila, meta anterior)."""
    key = scope_key(year, month, municipality, template_id, gestor_user_id, unit)
    row = db.query(PlannerTarget).filter(PlannerTarget.project_id == project_id, PlannerTarget.scope_key == key).first()
    previous = row.target if row else None
    if row is None:
        new_value = value
    elif mode == "create":
        return ("unchanged" if row.target == value else "exists"), row, previous
    else:
        new_value = row.target + value if mode == "add" else value
        if new_value == row.target:
            return "unchanged", row, previous
        if not (reason or "").strip():
            raise HTTPException(status_code=422, detail="Cambiar una meta existente exige justificación")
    before = target_dict(row) if row else None
    if row is None:
        row = PlannerTarget(project_id=project_id, year=year, month=month, municipality=municipality.strip(), template_id=template_id,
                            gestor_user_id=gestor_user_id, unit=unit, target=new_value, scope_key=key, updated_by=user_id)
        db.add(row)
        db.flush()
        outcome = "created"
    else:
        row.target = new_value
        row.version += 1
        row.updated_by = user_id
        row.updated_at = utc_now()
        outcome = "added" if mode == "add" else "replaced"
    _history(db, project_id, "target", row.id, before, target_dict(row), reason, user_id, source, client_ref)
    return outcome, row, previous


# ── Importación masiva de metas ───────────────────────────────────────────

TEMPLATE_HEADERS = ["anio", "mes", "municipio", "formulario", "gestor", "unidad", "meta", "modo", "justificacion"]
HEADER_ALIASES = {"año": "anio", "ano": "anio", "year": "anio", "month": "mes", "municipality": "municipio", "actividad": "formulario",
                  "form": "formulario", "template": "formulario", "unit": "unidad", "target": "meta", "mode": "modo",
                  "justificación": "justificacion", "reason": "justificacion", "correo_gestor": "gestor"}
UNIT_ALIASES = {"": "records", "registros": "records", "actividades": "records", "visitas": "records", "records": "records",
                "familias": "families", "familias unicas": "families", "familias únicas": "families", "families": "families"}


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow([date.today().year, 11, "Turbo", "Visita 3 FSC", "gestor@ejemplo.org", "registros", 100, "crear", ""])
    return "﻿" + buffer.getvalue()


def read_rows(filename: str, content: bytes) -> list[dict[str, str]]:
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).worksheets[0]
        rows = [["" if cell is None else str(cell).strip() for cell in row] for row in sheet.iter_rows(values_only=True)]
    elif name.endswith(".csv"):
        text = content.decode("utf-8-sig")
        dialect = csv.Sniffer().sniff(text.splitlines()[0] if text else ",", delimiters=",;\t")
        rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text), dialect)]
    else:
        raise HTTPException(status_code=422, detail="Sube un archivo .xlsx o .csv")
    rows = [row for row in rows if any(row)]
    if not rows:
        raise HTTPException(status_code=422, detail="El archivo está vacío")
    headers = [HEADER_ALIASES.get(norm(h), norm(h)) for h in rows[0]]
    missing = [h for h in ("anio", "mes", "municipio", "formulario", "meta") if h not in headers]
    if missing:
        raise HTTPException(status_code=422, detail=f"Faltan columnas obligatorias: {', '.join(missing)}")
    if len(rows) > 5001:
        raise HTTPException(status_code=422, detail="Máximo 5.000 filas por archivo")
    return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in rows[1:]]


def import_targets(db: Session, project_id: str, scope: PlannerScope, filename: str, content: bytes, preview_only: bool) -> dict:
    require_manage(scope)
    rows = read_rows(filename, content)
    file_hash = hashlib.sha256(content).hexdigest()[:40]
    templates = db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id).all()
    by_id = {t.id: t for t in templates}
    by_name: dict[str, list[BuilderTemplate]] = defaultdict(list)
    for template in templates:
        by_name[norm(template.name)].append(template)
    project_users = _project_users(db, project_id)
    applied_refs = {row[0] for row in db.query(PlannerHistory.client_ref).filter(PlannerHistory.project_id == project_id,
                                                                                  PlannerHistory.client_ref.like(f"{file_hash}:%")).all()}
    closed: dict[int, set[int]] = {}
    seen: dict[str, int] = {}
    results = []
    before_total = after_total = 0
    for index, raw in enumerate(rows, start=2):
        line = {"row": index, "status": "error", "message": "", "before": None, "after": None}
        try:
            year, month = int(float(raw.get("anio") or 0)), int(float(raw.get("mes") or 0))
            if not 2000 <= year <= 2100 or not 1 <= month <= 12:
                raise ValueError("Año o mes no válido")
            if month in closed.setdefault(year, closed_months(db, project_id, year)):
                raise ValueError("Ese mes tiene un corte cerrado; sus metas no se modifican")
            municipality = (raw.get("municipio") or "").strip()
            if not municipality:
                raise ValueError("Falta el municipio")
            if not scope.sees_municipality(municipality):
                raise ValueError("Municipio fuera de tu territorio autorizado")
            form_ref = (raw.get("formulario") or "").strip()
            matches = [by_id[form_ref]] if form_ref in by_id else by_name.get(norm(form_ref), [])
            if len(matches) != 1:
                raise ValueError("Formulario no encontrado" if not matches else "Hay varios formularios con ese nombre; usa su ID")
            template = matches[0]
            gestor_id = None
            gestor_ref = norm(raw.get("gestor"))
            if gestor_ref:
                gestor_id = project_users.get(gestor_ref)
                if not gestor_id:
                    raise ValueError("El gestor no existe, está inactivo o no pertenece al proyecto")
            unit = UNIT_ALIASES.get(norm(raw.get("unidad")))
            if unit is None:
                raise ValueError("Unidad no válida: usa registros o familias")
            meta_raw = (raw.get("meta") or "").replace(",", ".")
            value = float(meta_raw)
            if value < 0 or value != int(value):
                raise ValueError("La meta debe ser un entero mayor o igual a cero")
            value = int(value)
            mode = IMPORT_MODES.get(norm(raw.get("modo")) or "crear")
            if mode is None:
                raise ValueError("Modo no válido: crear, reemplazar o sumar")
            reason = (raw.get("justificacion") or "").strip()
            key = scope_key(year, month, municipality, template.id, gestor_id, unit)
            if key in seen:
                raise ValueError(f"Duplicada con la fila {seen[key]}")
            seen[key] = index
            client_ref = f"{file_hash}:{index}"
            existing = db.query(PlannerTarget).filter(PlannerTarget.project_id == project_id, PlannerTarget.scope_key == key).first()
            line["before"] = existing.target if existing else None
            line.update({"year": year, "month": month, "municipality": municipality, "template": template.name, "unit": unit})
            if client_ref in applied_refs:
                line.update({"status": "already_applied", "message": "Esta fila de este archivo ya se aplicó", "after": line["before"]})
            elif mode != "create" and existing and not reason:
                raise ValueError("Reemplazar o sumar una meta existente exige justificación")
            elif existing is None:
                line.update({"status": "create", "after": value})
            elif mode == "create":
                line.update({"status": "unchanged" if existing.target == value else "exists",
                             "message": "" if existing.target == value else "Ya existe una meta; usa modo reemplazar o sumar", "after": existing.target})
            else:
                after = existing.target + value if mode == "add" else value
                line.update({"status": "unchanged" if after == existing.target else ("add" if mode == "add" else "replace"), "after": after})
            line["_apply"] = (year, month, municipality, template.id, gestor_id, unit, value, mode, reason, client_ref) if line["status"] in {"create", "add", "replace"} else None
        except (ValueError, TypeError) as exc:
            line.update({"status": "error", "message": str(exc) if str(exc) else "Fila no válida", "_apply": None})
        before_total += line["before"] or 0
        after_total += (line["after"] if line["after"] is not None else line["before"]) or 0
        results.append(line)
    errors = sum(1 for line in results if line["status"] in {"error", "exists"})
    applied = 0
    if not preview_only:
        if errors:
            raise HTTPException(status_code=422, detail="Corrige las filas con error antes de aplicar")
        for line in results:
            if line["_apply"]:
                year, month, municipality, template_id, gestor_id, unit, value, mode, reason, client_ref = line["_apply"]
                apply_target(db, project_id, scope.user_id, year=year, month=month, municipality=municipality, template_id=template_id,
                             gestor_user_id=gestor_id, unit=unit, value=value, mode=mode, reason=reason or "Importación", source="import",
                             client_ref=client_ref)
                applied += 1
        db.commit()
    for line in results:
        line.pop("_apply", None)
    return {"rows": results, "errors": errors, "applied": applied, "total_before": before_total, "total_after": after_total, "preview_only": preview_only}


def errors_csv(result: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["fila", "estado", "mensaje"])
    for line in result["rows"]:
        if line["status"] in {"error", "exists"}:
            writer.writerow([line["row"], line["status"], line["message"]])
    return "﻿" + buffer.getvalue()


def _project_users(db: Session, project_id: str) -> dict[str, str]:
    from app.api.v1.gestor_teams import _project_user_ids
    ids = _project_user_ids(db, project_id)
    return {norm(user.email): user.id for user in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}


# ── Plan del gestor ───────────────────────────────────────────────────────


def plan_dict(row: PlannerPlan) -> dict:
    return {"id": row.id, "gestor_user_id": row.gestor_user_id, "template_id": row.template_id, "municipality": row.municipality,
            "coordinator_user_id": row.coordinator_user_id, "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
            "planned_quantity": row.planned_quantity, "planned_participants": row.planned_participants, "status": row.status,
            "note": row.note, "version": row.version}


def create_plan(db: Session, project_id: str, scope: PlannerScope, data: dict) -> PlannerPlan:
    gestor_id = data.get("gestor_user_id") or scope.user_id
    if gestor_id != scope.user_id and not scope.can_manage:
        raise HTTPException(status_code=403, detail="Solo puedes programar tus propias actividades")
    _validate_plan_dates(data["start_date"], data["end_date"])
    template = db.get(BuilderTemplate, data["template_id"])
    if template is None or template.project_id != project_id:
        raise HTTPException(status_code=422, detail="Formulario no encontrado en el proyecto")
    municipality = gestor_municipality(db, project_id, gestor_id) or (data.get("municipality") or "").strip()
    if municipality and not scope.sees_municipality(municipality):
        raise HTTPException(status_code=403, detail="Municipio fuera de tu territorio autorizado")
    row = PlannerPlan(project_id=project_id, gestor_user_id=gestor_id, template_id=template.id, municipality=municipality,
                      coordinator_user_id=coordinator_by_gestor(db, project_id).get(gestor_id),
                      start_date=data["start_date"], end_date=data["end_date"],
                      planned_quantity=data.get("planned_quantity") or 0, planned_participants=data.get("planned_participants") or 0,
                      note=(data.get("note") or "").strip() or None, created_by=scope.user_id)
    db.add(row)
    db.flush()
    _history(db, project_id, "plan", row.id, None, plan_dict(row), data.get("note"), scope.user_id)
    db.commit()
    return row


def _validate_plan_dates(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(status_code=422, detail="La fecha final no puede ser anterior a la inicial")


def change_plan(db: Session, scope: PlannerScope, plan: PlannerPlan, data: dict, *, cancel: bool = False) -> PlannerPlan:
    if plan.gestor_user_id != scope.user_id and not scope.can_manage:
        raise HTTPException(status_code=403, detail="Solo puedes reprogramar tus propias actividades")
    if not (data.get("reason") or "").strip():
        raise HTTPException(status_code=422, detail="Reprogramar o cancelar exige justificación")
    if plan.status == "cancelled":
        raise HTTPException(status_code=409, detail="La actividad ya está cancelada")
    before = plan_dict(plan)
    if cancel:
        plan.status = "cancelled"
    else:
        start, end = data.get("start_date") or plan.start_date, data.get("end_date") or plan.end_date
        _validate_plan_dates(start, end)
        plan.start_date, plan.end_date = start, end
        if data.get("planned_quantity") is not None:
            plan.planned_quantity = data["planned_quantity"]
        if data.get("planned_participants") is not None:
            plan.planned_participants = data["planned_participants"]
        plan.status = "rescheduled"
    plan.version += 1
    plan.updated_at = utc_now()
    _history(db, plan.project_id, "plan", plan.id, before, plan_dict(plan), data["reason"], scope.user_id)
    db.commit()
    return plan


# ── Población objetivo ────────────────────────────────────────────────────


def upsert_population(db: Session, project_id: str, scope: PlannerScope, data: dict) -> PlannerPopulation:
    require_manage(scope)
    municipality = (data.get("municipality") or "").strip()
    if not municipality or not scope.sees_municipality(municipality):
        raise HTTPException(status_code=422, detail="Municipio no válido o fuera de tu territorio")
    rows = db.query(PlannerPopulation).filter(PlannerPopulation.project_id == project_id, PlannerPopulation.year == data["year"]).all()
    row = next((item for item in rows if norm(item.municipality) == norm(municipality)), None)
    before = None
    if row is None:
        row = PlannerPopulation(project_id=project_id, year=data["year"], municipality=municipality, updated_by=scope.user_id)
        db.add(row)
    else:
        if not (data.get("reason") or "").strip():
            raise HTTPException(status_code=422, detail="Cambiar la población objetivo exige justificación")
        before = {"families": row.families, "participants": row.participants, "version": row.version}
        row.version += 1
    row.families, row.participants = data.get("families") or 0, data.get("participants") or 0
    row.source = (data.get("source") or "").strip() or None
    row.updated_by, row.updated_at = scope.user_id, utc_now()
    db.flush()
    _history(db, project_id, "population", row.id, before, {"year": row.year, "municipality": row.municipality, "families": row.families,
                                                              "participants": row.participants, "version": row.version}, data.get("reason"), scope.user_id)
    db.commit()
    return row


# ── Tablero y reportes ────────────────────────────────────────────────────


def month_data(db: Session, project_id: str, year: int, settings: PlannerSettings) -> tuple[list[dict], list[dict], set[int]]:
    """Hechos y metas del año; los meses con corte cerrado salen de su foto."""
    cuts = {cut.month: json.loads(cut.snapshot_json) for cut in db.query(PlannerCut).filter(PlannerCut.project_id == project_id, PlannerCut.year == year).all()}
    live_facts = [fact_dict(fact) for fact in compute_facts(db, project_id, year, settings)]
    live_targets = [target_dict(row) for row in db.query(PlannerTarget).filter(PlannerTarget.project_id == project_id, PlannerTarget.year == year).all()]
    facts = [fact for fact in live_facts if fact["month"] not in cuts]
    targets = [target for target in live_targets if target["month"] not in cuts]
    for snapshot in cuts.values():
        facts.extend(snapshot["facts"])
        targets.extend(snapshot["targets"])
    return facts, targets, set(cuts)


def fact_dict(fact: Fact) -> dict:
    return {"month": fact.month, "municipality": fact.municipality, "template_id": fact.template_id, "gestor_user_id": fact.gestor_user_id,
            "coordinator_user_id": fact.coordinator_user_id, "records": fact.records, "families": sorted(fact.families)}


def close_cut(db: Session, project_id: str, scope: PlannerScope, year: int, month: int) -> PlannerCut:
    require_manage(scope)
    if db.query(PlannerCut.id).filter(PlannerCut.project_id == project_id, PlannerCut.year == year, PlannerCut.month == month).first():
        raise HTTPException(status_code=409, detail="Ese mes ya tiene un corte cerrado")
    settings = get_settings(db, project_id)
    facts = [fact_dict(fact) for fact in compute_facts(db, project_id, year, settings) if fact.month == month]
    targets = [target_dict(row) for row in db.query(PlannerTarget).filter(PlannerTarget.project_id == project_id, PlannerTarget.year == year,
                                                                          PlannerTarget.month == month).all()]
    cut = PlannerCut(project_id=project_id, year=year, month=month, snapshot_json=json.dumps({"facts": facts, "targets": targets}, ensure_ascii=False),
                     settings_json=json.dumps(_settings_dict(settings), ensure_ascii=False), closed_by=scope.user_id)
    db.add(cut)
    db.commit()
    return cut


@dataclass
class Filters:
    year: int
    month: int | None = None
    municipality: str | None = None
    gestor_user_id: str | None = None
    coordinator_user_id: str | None = None
    template_id: str | None = None

    def keep(self, row: dict) -> bool:
        return ((self.month is None or row["month"] == self.month)
                and (not self.municipality or norm(row["municipality"]) == norm(self.municipality))
                and (not self.template_id or row["template_id"] == self.template_id)
                and (not self.gestor_user_id or row.get("gestor_user_id") == self.gestor_user_id)
                and (not self.coordinator_user_id or row.get("coordinator_user_id") == self.coordinator_user_id))


def _metric(target: int, executed: int) -> dict:
    return {"target": target, "executed": executed, "pending": max(target - executed, 0), "over": max(executed - target, 0),
            "compliance": compliance(executed, target)}


def build_report(db: Session, project_id: str, scope: PlannerScope, filters: Filters) -> dict:
    settings = get_settings(db, project_id)
    facts, targets, closed = month_data(db, project_id, filters.year, settings)
    coordinators = coordinator_by_gestor(db, project_id)
    for target in targets:
        target.setdefault("coordinator_user_id", coordinators.get(target.get("gestor_user_id") or ""))
    visible = lambda row: scope.sees_municipality(row["municipality"]) and (scope.supervise or row.get("gestor_user_id") == scope.user_id)  # noqa: E731
    facts = [row for row in facts if visible(row) and filters.keep(row)]
    targets = [row for row in targets if (scope.sees_municipality(row["municipality"]) or not row["municipality"])
               and (scope.supervise or row.get("gestor_user_id") == scope.user_id) and filters.keep(row)]

    plans = db.query(PlannerPlan).filter(PlannerPlan.project_id == project_id, PlannerPlan.status != "cancelled").all()
    names = _names(db, project_id, facts, targets, plans)
    # 1. Resumen municipal (mes × municipio × actividad). La meta municipal
    # explícita (sin gestor) manda; si no hay, se suman las de los gestores.
    municipal: dict[tuple, dict] = {}

    def bucket(store: dict, key: tuple, base: dict) -> dict:
        if key not in store:
            store[key] = {**base, "records": 0, "families": set(), "t_records_muni": None, "t_records_gestor": 0,
                          "t_families_muni": None, "t_families_gestor": 0}
        return store[key]

    for fact in facts:
        item = bucket(municipal, (fact["month"], norm(fact["municipality"]), fact["template_id"]),
                      {"month": fact["month"], "municipality": fact["municipality"], "template_id": fact["template_id"]})
        item["records"] += fact["records"]
        item["families"].update(fact["families"])
    for target in targets:
        item = bucket(municipal, (target["month"], norm(target["municipality"]), target["template_id"]),
                      {"month": target["month"], "municipality": target["municipality"], "template_id": target["template_id"]})
        prefix = "t_records" if target["unit"] == "records" else "t_families"
        if target.get("gestor_user_id"):
            item[f"{prefix}_gestor"] += target["target"]
        else:
            item[f"{prefix}_muni"] = (item[f"{prefix}_muni"] or 0) + target["target"]
    population = {(row.year, norm(row.municipality)): row for row in db.query(PlannerPopulation).filter(
        PlannerPopulation.project_id == project_id, PlannerPopulation.year == filters.year).all()}
    summary_rows = []
    for item in sorted(municipal.values(), key=lambda r: (r["month"], norm(r["municipality"]), names["templates"].get(r["template_id"], ""))):
        records_target = item["t_records_muni"] if item["t_records_muni"] is not None else item["t_records_gestor"]
        families_target = item["t_families_muni"] if item["t_families_muni"] is not None else item["t_families_gestor"]
        pop = population.get((filters.year, norm(item["municipality"])))
        summary_rows.append({
            "month": item["month"], "municipality": item["municipality"] or "Sin municipio", "template_id": item["template_id"],
            "activity": names["templates"].get(item["template_id"], item["template_id"]),
            "population_families": pop.families if pop else None, "population_participants": pop.participants if pop else None,
            "activities": _metric(records_target, item["records"]), "families": _metric(families_target, len(item["families"])),
            "closed": item["month"] in closed,
        })

    # 2. Detalle por gestor (mes × gestor × municipio × actividad).
    plan_by_key: dict[tuple, list[PlannerPlan]] = defaultdict(list)
    for plan in plans:
        for month in _months_between(plan.start_date, plan.end_date, filters.year):
            plan_by_key[(month, plan.gestor_user_id, plan.template_id)].append(plan)
    detail: dict[tuple, dict] = {}
    for fact in facts:
        key = (fact["month"], fact.get("gestor_user_id"), norm(fact["municipality"]), fact["template_id"])
        row = detail.setdefault(key, {"month": fact["month"], "gestor_user_id": fact.get("gestor_user_id"), "coordinator_user_id": fact.get("coordinator_user_id"),
                                      "municipality": fact["municipality"], "template_id": fact["template_id"], "records": 0, "families": set(),
                                      "target_records": 0, "target_families": 0})
        row["records"] += fact["records"]
        row["families"].update(fact["families"])
    for target in targets:
        if not target.get("gestor_user_id"):
            continue
        key = (target["month"], target["gestor_user_id"], norm(target["municipality"]), target["template_id"])
        row = detail.setdefault(key, {"month": target["month"], "gestor_user_id": target["gestor_user_id"], "coordinator_user_id": target.get("coordinator_user_id"),
                                      "municipality": target["municipality"], "template_id": target["template_id"], "records": 0, "families": set(),
                                      "target_records": 0, "target_families": 0})
        row["target_records" if target["unit"] == "records" else "target_families"] += target["target"]
    # Lo programado aparece aunque aún no tenga meta ni ejecución.
    for (month, gestor_id, template_id), planned in plan_by_key.items():
        plan = planned[0]
        probe = {"month": month, "municipality": plan.municipality, "template_id": template_id, "gestor_user_id": gestor_id,
                 "coordinator_user_id": plan.coordinator_user_id}
        if not (scope.sees_gestor(gestor_id) and (not plan.municipality or scope.sees_municipality(plan.municipality)) and filters.keep(probe)):
            continue
        detail.setdefault((month, gestor_id, norm(plan.municipality), template_id), {
            "month": month, "gestor_user_id": gestor_id, "coordinator_user_id": plan.coordinator_user_id, "municipality": plan.municipality,
            "template_id": template_id, "records": 0, "families": set(), "target_records": 0, "target_families": 0})
    detail_rows = []
    for row in sorted(detail.values(), key=lambda r: (r["month"], names["users"].get(r["gestor_user_id"] or "", ""), names["templates"].get(r["template_id"], ""))):
        planned = plan_by_key.get((row["month"], row["gestor_user_id"], row["template_id"]), [])
        metric = _metric(row["target_records"], row["records"])
        detail_rows.append({
            "month": row["month"], "coordinator": names["users"].get(row["coordinator_user_id"] or "", ""),
            "gestor": names["users"].get(row["gestor_user_id"] or "", "Sin gestor"), "gestor_user_id": row["gestor_user_id"],
            "gestor_document": names["profiles"].get(row["gestor_user_id"] or "", {}).get("document_id", ""),
            "gestor_position": names["profiles"].get(row["gestor_user_id"] or "", {}).get("position", ""),
            "municipality": row["municipality"] or "Sin municipio", "activity": names["templates"].get(row["template_id"], row["template_id"]),
            "start_date": min((p.start_date for p in planned), default=None), "end_date": max((p.end_date for p in planned), default=None),
            "planned_quantity": sum(p.planned_quantity for p in planned), "planned_participants": sum(p.planned_participants for p in planned),
            "activities": metric, "families_executed": len(row["families"]), "families_target": row["target_families"],
            "state": _state(metric), "closed": row["month"] in closed,
        })

    # 3. Consolidado general: totales y acumulado del año (ponderados).
    # El cumplimiento solo mide lo que tiene meta; lo ejecutado sin meta se
    # informa aparte como «fuera de programación», para revisar.
    goaled = [r for r in summary_rows if r["activities"]["target"] > 0]
    total_target = sum(r["activities"]["target"] for r in goaled)
    total_goaled = sum(r["activities"]["executed"] for r in goaled)
    unplanned = sum(r["activities"]["executed"] for r in summary_rows if r["activities"]["target"] == 0)
    family_keys: dict[tuple, set[str]] = defaultdict(set)
    for fact in facts:
        family_keys[(fact["month"], norm(fact["municipality"]), fact["template_id"])].update(fact["families"])
    all_families = set().union(*family_keys.values()) if family_keys else set()
    families_goaled = set().union(*[family_keys[(r["month"], norm(r["municipality"]) if r["municipality"] != "Sin municipio" else "", r["template_id"])]
                                    for r in summary_rows if r["families"]["target"] > 0] or [set()])
    families_target = sum(r["families"]["target"] for r in summary_rows)
    population_total = sum(p.families for key, p in population.items() if scope.sees_municipality(p.municipality)
                           and (not filters.municipality or norm(p.municipality) == norm(filters.municipality)))
    by_month: dict[int, dict] = defaultdict(lambda: {"target": 0, "executed": 0, "unplanned": 0})
    for r in summary_rows:
        if r["activities"]["target"] > 0:
            by_month[r["month"]]["target"] += r["activities"]["target"]
            by_month[r["month"]]["executed"] += r["activities"]["executed"]
        else:
            by_month[r["month"]]["unplanned"] += r["activities"]["executed"]
    accumulated, running_target, running_executed = [], 0, 0
    for month in sorted(by_month):
        running_target += by_month[month]["target"]
        running_executed += by_month[month]["executed"]
        accumulated.append({"month": month, **_metric(by_month[month]["target"], by_month[month]["executed"]),
                            "unplanned": by_month[month]["unplanned"], "accumulated": _metric(running_target, running_executed)})
    # Mismas metas que el resumen municipal (los totales cuadran); el
    # coordinador se toma de los gestores que ejecutaron o tienen meta.
    coordinators_by_row: dict[tuple, set[str]] = defaultdict(set)
    for r in detail_rows:
        if r["coordinator"]:
            coordinators_by_row[(r["month"], norm(r["municipality"]), r["activity"])].add(r["coordinator"])
    general_rows = [{"month": r["month"], "municipality": r["municipality"], "activity": r["activity"],
                     "coordinator": ", ".join(sorted(coordinators_by_row.get((r["month"], norm(r["municipality"]), r["activity"]), set()))) or "Sin coordinador",
                     **r["activities"]} for r in summary_rows]
    return {
        "year": filters.year, "settings": _settings_dict(settings), "closed_months": sorted(closed),
        "totals": {"activities": {**_metric(total_target, total_goaled), "unplanned": unplanned, "all_executed": total_goaled + unplanned},
                   "families": {**_metric(families_target, len(families_goaled)), "unique_all": len(all_families),
                                "population": population_total or None,
                                "coverage": compliance(len(all_families), population_total) if population_total else None}},
        "municipal": summary_rows, "gestor": detail_rows, "general": general_rows, "by_month": accumulated,
    }


def _state(metric: dict) -> str:
    if metric["compliance"] is None:
        return "Sin meta" if metric["executed"] == 0 else "Sobre-ejecución sin meta"
    if metric["executed"] >= metric["target"]:
        return "Cumplido" if metric["executed"] == metric["target"] else "Sobre-ejecución"
    return "Pendiente"


def _months_between(start: date, end: date, year: int) -> list[int]:
    first = 1 if start.year < year else start.month
    last = 12 if end.year > year else end.month
    return list(range(first, last + 1)) if start.year <= year <= end.year else []


def _names(db: Session, project_id: str, facts: list[dict], targets: list[dict], plans: list[PlannerPlan]) -> dict:
    templates = {t.id: t.name for t in db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id).all()}
    user_ids = {r.get("gestor_user_id") for r in facts + targets} | {r.get("coordinator_user_id") for r in facts + targets}
    user_ids |= {p.gestor_user_id for p in plans} | {p.coordinator_user_id for p in plans}
    user_ids.discard(None)
    people = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    return {"templates": templates, "users": {u.id: u.full_name for u in people},
            "profiles": {u.id: {"document_id": u.document_id, "position": u.position or "", "municipality": u.municipality or ""} for u in people}}


MONTHS = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _pct(value: float | None) -> str | float:
    return "Sin meta" if value is None else value / 100


def export_xlsx(report: dict) -> bytes:
    """Un solo .xlsx con las tres hojas, mismo corte, filtros y permisos que el tablero."""
    book = Workbook()
    header_font, header_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="0F766E")

    def sheet(ws, headers: list[str], rows: list[list], percent_cols: set[int]) -> None:
        ws.append(headers)
        for cell in ws[1]:
            cell.font, cell.fill = header_font, header_fill
        for row in rows:
            ws.append(row)
        for col in percent_cols:
            for cell in ws.iter_cols(min_col=col, max_col=col, min_row=2):
                for item in cell:
                    if isinstance(item.value, float):
                        item.number_format = "0.00%"
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = max(12, min(40, max(len(str(c.value or "")) for c in column) + 2))
        ws.freeze_panes = "A2"

    ws = book.active
    ws.title = "Resumen municipal"
    sheet(ws, ["Mes", "Municipio", "Actividad", "Población objetivo (familias)", "Meta", "Ejecutado válido", "Pendiente", "% cumplimiento",
               "Meta familias", "Familias únicas", "% familias", "Corte"],
          [[MONTHS[r["month"]], r["municipality"], r["activity"], r["population_families"], r["activities"]["target"], r["activities"]["executed"],
            r["activities"]["pending"], _pct(r["activities"]["compliance"]), r["families"]["target"], r["families"]["executed"],
            _pct(r["families"]["compliance"]), "Cerrado" if r["closed"] else "Vivo"] for r in report["municipal"]], {8, 11})
    sheet(book.create_sheet("Detalle por gestor"),
          ["Mes", "Coordinador", "Gestor", "Documento", "Cargo", "Municipio", "Actividad", "Fecha inicio", "Fecha fin", "Programado",
           "Participantes previstos", "Meta", "Ejecutado", "Pendiente", "% cumplimiento", "Familias únicas", "Estado"],
          [[MONTHS[r["month"]], r["coordinator"], r["gestor"], r["gestor_document"], r["gestor_position"], r["municipality"], r["activity"],
            r["start_date"], r["end_date"], r["planned_quantity"], r["planned_participants"], r["activities"]["target"], r["activities"]["executed"],
            r["activities"]["pending"], _pct(r["activities"]["compliance"]), r["families_executed"], r["state"]] for r in report["gestor"]], {15})
    general = book.create_sheet("Consolidado general")
    rows = [[MONTHS[r["month"]], r["municipality"], r["coordinator"], r["activity"], r["target"], r["executed"], r["pending"], _pct(r["compliance"])]
            for r in report["general"]]
    rows.append([])
    rows.append(["Acumulado del año", "", "", "", "", "", "", ""])
    rows.extend([[MONTHS[m["month"]], "", "", "Total del mes", m["target"], m["executed"], m["pending"], _pct(m["compliance"]),
                  m["accumulated"]["target"], m["accumulated"]["executed"], _pct(m["accumulated"]["compliance"])] for m in report["by_month"]])
    totals = report["totals"]
    rows.append([])
    rows.append(["Total", "", "", "Actividades (visitas)", totals["activities"]["target"], totals["activities"]["executed"],
                 totals["activities"]["pending"], _pct(totals["activities"]["compliance"])])
    rows.append(["Total", "", "", "Ejecutado fuera de programación (sin meta, a revisar)", "", totals["activities"]["unplanned"], "", ""])
    rows.append(["Total", "", "", "Familias únicas", totals["families"]["target"], totals["families"]["executed"],
                 totals["families"]["pending"], _pct(totals["families"]["compliance"])])
    if totals["families"]["population"]:
        rows.append(["Cobertura", "", "", "Familias únicas / población objetivo", totals["families"]["population"],
                     totals["families"]["unique_all"], "", _pct(totals["families"]["coverage"])])
    sheet(general, ["Mes", "Municipio", "Coordinador", "Actividad", "Meta", "Ejecutado", "Pendiente", "% cumplimiento", "Meta acumulada",
                    "Ejecutado acumulado", "% acumulado"], rows, {8, 11})
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()
