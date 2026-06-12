from pydantic import BaseModel


class ProjectAccessResponse(BaseModel):
    project_id: str
    user_id: str
    has_access: bool
