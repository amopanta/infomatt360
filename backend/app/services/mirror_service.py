"""Base Espejo real: replicacion de RuntimeRecord/RuntimeRecordValue hacia una
base de datos externa (Postgres o SQLite por ahora, ver docs/102).

Las credenciales de conexion nunca se guardan en texto plano -- se cifran con
app.core.security.encrypt_text, mismo mecanismo usado para credenciales S3
(app/services/s3_storage_service.py) y tokens OAuth de Google Drive.
"""

import json
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, select, text
from sqlalchemy.orm import Session

from app.core.security import decrypt_text, encrypt_text
from app.core.time import utc_now
from app.models.mirror import MirrorPlan, MirrorRun, MirrorTarget
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.mirror import (
    MirrorPlanCreate,
    MirrorPlanRead,
    MirrorRunRead,
    MirrorTargetConnect,
    MirrorTargetRead,
    MirrorTargetTestConnectionResult,
)


def target_to_read(row: MirrorTarget) -> MirrorTargetRead:
    return MirrorTargetRead(id=row.id, project_id=row.project_id, name=row.name, engine=row.engine, status=row.status)


def plan_to_read(row: MirrorPlan) -> MirrorPlanRead:
    return MirrorPlanRead(id=row.id, target_id=row.target_id, name=row.name, schedule_mode=row.schedule_mode, status=row.status, last_result=row.last_result)


def run_to_read(row: MirrorRun) -> MirrorRunRead:
    return MirrorRunRead(
        id=row.id,
        plan_id=row.plan_id,
        status=row.status,
        records_synced=row.records_synced,
        values_synced=row.values_synced,
        triggered_by=row.triggered_by,
        error=row.error,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _build_url(engine: str, credentials: dict) -> str:
    if engine == "postgres":
        host = credentials.get("host")
        database = credentials.get("database")
        username = credentials.get("username")
        if not host or not database or not username:
            raise ValueError("Faltan datos de conexion para Postgres (host, database, username)")
        port = credentials.get("port") or 5432
        password = credentials.get("password") or ""
        return f"postgresql+psycopg2://{quote(username)}:{quote(password)}@{host}:{port}/{database}"
    if engine == "sqlite":
        file_path = credentials.get("file_path")
        if not file_path:
            raise ValueError("Falta file_path para el motor SQLite")
        return f"sqlite:///{file_path}"
    raise ValueError(f"Motor no soportado: {engine}")


def _mirror_tables() -> tuple[MetaData, Table, Table]:
    """Estructura equivalente (EAV) que se crea/usa en la base espejo.

    Prefijo im360_ para no chocar con tablas propias del cliente en la base
    destino -- el espejo puede compartir base de datos con otros usos.
    """
    metadata = MetaData()
    records_table = Table(
        "im360_runtime_records",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("project_id", String(36), nullable=False),
        Column("template_id", String(36), nullable=False),
        Column("status", String(40), nullable=False),
        Column("participant_id", String(36), nullable=True),
        Column("submitted_by", String(36), nullable=True),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    values_table = Table(
        "im360_runtime_record_values",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("record_id", String(36), nullable=False),
        Column("field_name", String(180), nullable=False),
        Column("field_value_json", Text, nullable=False),
        Column("created_at", DateTime, nullable=False),
    )
    return metadata, records_table, values_table


def _record_row(record: RuntimeRecord) -> dict:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "template_id": record.template_id,
        "status": record.status,
        "participant_id": record.participant_id,
        "submitted_by": record.submitted_by,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _value_row(value: RuntimeRecordValue) -> dict:
    return {
        "id": value.id,
        "record_id": value.record_id,
        "field_name": value.field_name,
        "field_value_json": value.field_value_json,
        "created_at": value.created_at,
    }


class MirrorService:
    def connect_target(self, db: Session, payload: MirrorTargetConnect) -> MirrorTargetRead:
        credentials = {
            "host": payload.host,
            "port": payload.port,
            "database": payload.database,
            "username": payload.username,
            "password": payload.password,
            "file_path": payload.file_path,
        }
        try:
            _build_url(payload.engine, credentials)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

        row = MirrorTarget(
            project_id=payload.project_id,
            name=payload.name,
            engine=payload.engine,
            conn_json=encrypt_text(json.dumps(credentials)),
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return target_to_read(row)

    def list_targets(self, db: Session, project_id: str) -> list[MirrorTargetRead]:
        rows = db.query(MirrorTarget).filter(MirrorTarget.project_id == project_id).order_by(MirrorTarget.created_at.desc()).all()
        return [target_to_read(row) for row in rows]

    def get_target(self, db: Session, target_id: str) -> MirrorTarget | None:
        return db.query(MirrorTarget).filter(MirrorTarget.id == target_id).first()

    def get_plan(self, db: Session, plan_id: str) -> MirrorPlan | None:
        return db.query(MirrorPlan).filter(MirrorPlan.id == plan_id).first()

    def _engine_for_target(self, target: MirrorTarget):
        credentials = json.loads(decrypt_text(target.conn_json))
        url = _build_url(target.engine, credentials)
        return create_engine(url)

    def test_connection(self, db: Session, target_id: str) -> MirrorTargetTestConnectionResult:
        target = self.get_target(db, target_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destino de espejo no encontrado")

        engine = None
        try:
            engine = self._engine_for_target(target)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            target.status = "connection_error"
            db.commit()
            return MirrorTargetTestConnectionResult(success=False, message=f"No fue posible conectar: {exc}"[:500])
        finally:
            if engine is not None:
                engine.dispose()

        target.status = "active"
        db.commit()
        return MirrorTargetTestConnectionResult(success=True, message="Conexion exitosa.")

    def create_plan(self, db: Session, payload: MirrorPlanCreate) -> MirrorPlanRead:
        row = MirrorPlan(
            target_id=payload.target_id,
            name=payload.name,
            # Version inicial: siempre espeja runtime_records +
            # runtime_record_values completos, no hay seleccion de tablas
            # todavia (ver docs/102, "que sigue sin resolver").
            tables_json='["runtime_records", "runtime_record_values"]',
            schedule_mode=payload.schedule_mode,
            status=payload.status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return plan_to_read(row)

    def list_plans(self, db: Session, target_id: str) -> list[MirrorPlanRead]:
        rows = db.query(MirrorPlan).filter(MirrorPlan.target_id == target_id).order_by(MirrorPlan.created_at.desc()).all()
        return [plan_to_read(row) for row in rows]

    def list_runs(self, db: Session, plan_id: str) -> list[MirrorRunRead]:
        rows = db.query(MirrorRun).filter(MirrorRun.plan_id == plan_id).order_by(MirrorRun.started_at.desc()).all()
        return [run_to_read(row) for row in rows]

    def run_plan(self, db: Session, plan_id: str, triggered_by: str | None) -> MirrorRunRead:
        plan = self.get_plan(db, plan_id)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan de espejo no encontrado")
        target = self.get_target(db, plan.target_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destino de espejo no encontrado")

        run = MirrorRun(plan_id=plan.id, status="running", triggered_by=triggered_by)
        db.add(run)
        db.commit()
        db.refresh(run)

        engine = None
        try:
            engine = self._engine_for_target(target)
            metadata, records_table, values_table = _mirror_tables()
            metadata.create_all(engine, checkfirst=True)

            records = db.query(RuntimeRecord).filter(RuntimeRecord.project_id == target.project_id).all()
            record_ids = [record.id for record in records]
            values = (
                db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id.in_(record_ids)).all()
                if record_ids
                else []
            )

            with engine.begin() as conn:
                if plan.schedule_mode == "insert_only":
                    existing_record_ids = {
                        row[0] for row in conn.execute(select(records_table.c.id).where(records_table.c.project_id == target.project_id))
                    }
                    new_records = [record for record in records if record.id not in existing_record_ids]
                    if new_records:
                        conn.execute(records_table.insert(), [_record_row(record) for record in new_records])

                    existing_value_ids = {row[0] for row in conn.execute(select(values_table.c.id))}
                    new_values = [value for value in values if value.id not in existing_value_ids]
                    if new_values:
                        conn.execute(values_table.insert(), [_value_row(value) for value in new_values])

                    records_synced, values_synced = len(new_records), len(new_values)
                else:  # full_mirror
                    existing_record_ids = {
                        row[0] for row in conn.execute(select(records_table.c.id).where(records_table.c.project_id == target.project_id))
                    }
                    if existing_record_ids:
                        conn.execute(values_table.delete().where(values_table.c.record_id.in_(existing_record_ids)))
                        conn.execute(records_table.delete().where(records_table.c.project_id == target.project_id))
                    if records:
                        conn.execute(records_table.insert(), [_record_row(record) for record in records])
                    if values:
                        conn.execute(values_table.insert(), [_value_row(value) for value in values])
                    records_synced, values_synced = len(records), len(values)

            run.status = "completed"
            run.records_synced = records_synced
            run.values_synced = values_synced
            plan.last_result = f"completed: {records_synced} registros, {values_synced} valores"
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)[:4000]
            plan.last_result = f"failed: {run.error}"
        finally:
            if engine is not None:
                engine.dispose()

        run.finished_at = utc_now()
        db.commit()
        db.refresh(run)
        return run_to_read(run)


mirror_service = MirrorService()
