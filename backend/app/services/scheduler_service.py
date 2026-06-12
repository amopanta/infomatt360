from sqlalchemy.orm import Session

from app.models.scheduler import ScheduledTask, TaskRun
from app.schemas.scheduler import ScheduledTaskCreate, ScheduledTaskRead, TaskRunCreate, TaskRunRead


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
    )


def run_to_read(row: TaskRun) -> TaskRunRead:
    return TaskRunRead(id=row.id, task_id=row.task_id, status=row.status, result_text=row.result_text)


class SchedulerService:
    def create_task(self, db: Session, payload: ScheduledTaskCreate) -> ScheduledTaskRead:
        row = ScheduledTask(**payload.model_dump())
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


scheduler_service = SchedulerService()
