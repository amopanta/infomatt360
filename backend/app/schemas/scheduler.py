from pydantic import BaseModel


class ScheduledTaskCreate(BaseModel):
    project_id: str
    name: str
    task_type: str
    target_id: str | None = None
    frequency: str = "manual"
    config_json: str | None = None
    status: str = "active"


class ScheduledTaskRead(ScheduledTaskCreate):
    id: str
    last_result: str | None = None


class TaskRunCreate(BaseModel):
    task_id: str
    status: str = "pending"
    result_text: str | None = None


class TaskRunRead(TaskRunCreate):
    id: str
