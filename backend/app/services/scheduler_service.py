"""Tareas programadas y su ejecucion recurrente real.

`ScheduledTask` es generico (`task_type` + `frequency`), pero hoy el unico
consumidor real es el respaldo de base de datos (`task_type="backup"`,
ver `backend/app/models/backup.py`). `run_due_tasks()` es el disparador
que hacia falta: sin el, las filas de `ScheduledTask` quedaban guardadas
pero nunca se ejecutaban -- el respaldo "programable" en realidad solo se
disparaba con el boton manual de `POST /backups/run`. El worker CLI
`backend/app/cli/run_scheduled_tasks.py` llama a `run_due_tasks()` en un
ciclo, igual que `process_bulk_jobs.py` hace con los lotes bulk.
"""

import json
import re
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.messages import MailProfile
from app.models.messages import InternalMessage
from app.models.identity import User
from app.models.case_management import ParticipantCase, SavedExport
from app.models.scheduler import ScheduledTask, TaskRun
from app.schemas.scheduler import ScheduledTaskCreate, ScheduledTaskRead, TaskRunCreate, TaskRunRead
from app.services import imap_service
from app.services.backup_service import backup_service
from app.services.mirror_service import mirror_service
from app.services.saved_export_service import run_saved_export
from app.services.message_service import message_service
from app.services.whatsapp_service import whatsapp_service

# Frecuencias recurrentes soportadas por el worker. "manual" (el default del
# modelo) deliberadamente no aparece aqui: una tarea manual nunca es "due",
# solo se dispara desde el boton de la web.
def task_schedule(task: ScheduledTask) -> tuple[str | None, str]:
    """Hora fija opcional en config_json: {"run_time": "02:00", "timezone": "America/Bogota"}."""
    try:
        config = json.loads(task.config_json or "{}")
    except ValueError:
        config = {}
    run_time = config.get("run_time") if isinstance(config, dict) else None
    timezone_name = (config.get("timezone") if isinstance(config, dict) else None) or "America/Bogota"
    return (run_time if isinstance(run_time, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", run_time) else None), timezone_name


def next_run_at(task: ScheduledTask, now: datetime, first: bool = False) -> datetime:
    """Próxima corrida en UTC sin zona. Diario/semanal con hora fija: la
    próxima vez que sea esa hora en la zona del proyecto; si no, el intervalo."""
    run_time, timezone_name = task_schedule(task)
    if not run_time or task.frequency not in {"daily", "weekly"}:
        return now if first else now + RECURRING_INTERVALS[task.frequency]
    from app.services.planner_service import resolve_timezone
    tz = resolve_timezone(timezone_name)
    local_now = now.replace(tzinfo=dt_timezone.utc).astimezone(tz)
    hour, minute = (int(part) for part in run_time.split(":"))
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    if task.frequency == "weekly" and not first:
        candidate += timedelta(days=6)
    return candidate.astimezone(dt_timezone.utc).replace(tzinfo=None)


RECURRING_INTERVALS: dict[str, timedelta] = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


def task_to_read(row: ScheduledTask) -> ScheduledTaskRead:
    return ScheduledTaskRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        task_type=row.task_type,
        target_id=row.target_id,
        frequency=row.frequency,
        config_json=row.config_json,
        status=row.status,
        last_result=row.last_result,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
    )


def run_to_read(row: TaskRun) -> TaskRunRead:
    return TaskRunRead(id=row.id, task_id=row.task_id, status=row.status, result_text=row.result_text)


class SchedulerService:
    def create_task(self, db: Session, payload: ScheduledTaskCreate) -> ScheduledTaskRead:
        row = ScheduledTask(**payload.model_dump())
        if row.frequency in RECURRING_INTERVALS and row.next_run_at is None:
            # Con hora fija (docs/146), la primera corrida es la próxima a esa
            # hora local; sin ella, el próximo ciclo del worker.
            row.next_run_at = next_run_at(row, utc_now(), first=True)
        db.add(row)
        db.commit()
        db.refresh(row)
        return task_to_read(row)

    def list_tasks(self, db: Session, project_id: str) -> list[ScheduledTaskRead]:
        rows = db.query(ScheduledTask).filter(ScheduledTask.project_id == project_id).order_by(ScheduledTask.created_at.desc()).all()
        return [task_to_read(row) for row in rows]

    def create_run(self, db: Session, payload: TaskRunCreate) -> TaskRunRead:
        row = TaskRun(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return run_to_read(row)

    def list_runs(self, db: Session, task_id: str) -> list[TaskRunRead]:
        rows = db.query(TaskRun).filter(TaskRun.task_id == task_id).order_by(TaskRun.started_at.desc()).all()
        return [run_to_read(row) for row in rows]

    def run_due_tasks(self, db: Session, limit: int = 50) -> dict[str, int]:
        """Ejecuta las tareas recurrentes activas cuyo `next_run_at` ya vencio.

        Disenado para llamarse en un ciclo desde un worker externo (CLI),
        no desde el proceso web -- un respaldo de PostgreSQL puede tomar
        minutos (`pg_dump`, timeout de 600s) y no debe bloquear una
        peticion HTTP.
        """
        now = utc_now()
        due = (
            db.query(ScheduledTask)
            .filter(
                ScheduledTask.status == "active",
                ScheduledTask.frequency.in_([*RECURRING_INTERVALS.keys(), "once"]),
                (ScheduledTask.next_run_at.is_(None)) | (ScheduledTask.next_run_at <= now),
            )
            .limit(limit)
            .all()
        )

        processed = succeeded = failed = 0
        for task in due:
            processed += 1
            status_value, result_text = self._execute(db, task)
            if status_value == "success":
                succeeded += 1
            else:
                failed += 1

            db.add(TaskRun(task_id=task.id, status=status_value, result_text=result_text, finished_at=utc_now()))
            task.last_run_at = now
            if task.frequency == "once":
                task.status = "completed" if status_value == "success" else "failed"
                task.next_run_at = None
            else:
                task.next_run_at = next_run_at(task, now)
            task.last_result = result_text
            db.commit()

        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    def _execute(self, db: Session, task: ScheduledTask) -> tuple[str, str]:
        if task.task_type == "backup":
            job = backup_service.run_backup(db, task.project_id, triggered_by=f"scheduler:{task.id}", storage_profile_id=task.target_id)
            if job.status == "completed":
                return "success", f"Respaldo completado: {job.file_path} ({job.size_bytes} bytes)"
            return "failed", job.error or "El respaldo fallo sin detalle de error"
        if task.task_type == "mail_poll":
            profile = db.query(MailProfile).filter(MailProfile.id == task.target_id).first()
            if profile is None:
                return "failed", "El perfil de correo IMAP referenciado ya no existe"
            return imap_service.poll_profile(db, profile)
        if task.task_type == "case_reminder":
            case = db.query(ParticipantCase).filter(ParticipantCase.id == task.target_id, ParticipantCase.project_id == task.project_id).first()
            if not case or not case.assigned_user_id or case.status == "closed":
                return "failed", "El caso ya no tiene un responsable o está cerrado"
            import json
            try:
                channels = json.loads(case.properties_json or "{}").get("_reminder_channels", ["internal"])
            except (ValueError, AttributeError):
                channels = ["internal"]
            if not isinstance(channels, list):
                channels = ["internal"]
            subject = f"Seguimiento pendiente: {case.title}"
            body = "El plazo de seguimiento de este caso ha llegado. Abre el participante para revisar el caso."
            results: list[str] = []
            if "internal" in channels:
                db.add(InternalMessage(project_id=case.project_id, recipient_id=case.assigned_user_id,
                                       subject=subject, body=body))
                results.append("interno: enviado")
            if "email" in channels:
                email_status, email_detail = message_service.send_project_email(db, case.project_id, case.assigned_user_id, subject, body)
                results.append(f"correo: {email_status} ({email_detail})")
            if "whatsapp" in channels:
                recipient = db.get(User, case.assigned_user_id)
                if recipient and recipient.phone:
                    notification = whatsapp_service.send_text(db, project_id=case.project_id, recipient_phone=recipient.phone,
                                                              recipient_user_id=recipient.id, message=f"{subject}\n{body}")
                    results.append(f"WhatsApp: {notification.status}")
                else:
                    results.append("WhatsApp: omitido (sin teléfono)")
            return "success", "; ".join(results) if results else "Sin canales de aviso seleccionados"
        if task.task_type == "saved_export":
            export = db.query(SavedExport).filter(SavedExport.id == task.target_id, SavedExport.project_id == task.project_id).first()
            if not export:
                return "failed", "La exportación guardada ya no existe"
            try:
                file = run_saved_export(db, export)
                return "success", f"Exportación disponible: {file.id}"
            except Exception as exc:
                db.rollback()
                return "failed", str(exc)
        if task.task_type == "mirror":
            from app.models.mirror import MirrorPlan
            plan = db.query(MirrorPlan).filter(MirrorPlan.id == task.target_id).first()
            if not plan:
                return "failed", "El plan de espejo referenciado ya no existe"
            try:
                run = mirror_service.run_plan(db, plan.id, triggered_by=f"scheduler:{task.id}")
                if run.status == "completed":
                    return "success", f"Espejo completado: {run.records_synced} registros, {run.values_synced} valores"
                if run.status == "completed_with_differences":
                    return "failed", f"Espejo completado con diferencias entre origen y destino: {plan.last_result}"
                return "failed", run.error or "El espejo fallo sin detalle de error"
            except Exception as exc:
                db.rollback()
                return "failed", str(exc)

        if task.task_type == "db_import":
            from app.models.db_import import DbImport
            from app.services.db_import_service import execute
            job = db.get(DbImport, task.target_id) if task.target_id else None
            if job is None:
                return "failed", "La importación referenciada ya no existe"
            if job.status != "active":
                return "failed", "La importación está en pausa"
            try:
                result = execute(db, job, triggered_by=f"scheduler:{task.id}")
                text_result = (f"{result['rows_read']} leídas, {result['created']} creadas, {result['updated']} actualizadas, "
                               f"{result['unchanged']} sin cambios, {result['failed']} con error")
                return ("success" if not result["failed"] else "failed"), text_result
            except Exception as exc:  # noqa: BLE001 - se registra en el historial de la tarea
                db.rollback()
                return "failed", str(getattr(exc, "detail", exc))
        return "failed", f"task_type '{task.task_type}' no esta soportado por el worker de tareas programadas"


scheduler_service = SchedulerService()
