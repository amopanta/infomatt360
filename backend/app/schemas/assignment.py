from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    user_id: str
    project_id: str
    role_id: str | None = None
    status: str = "active"


class AssignmentRead(AssignmentCreate):
    id: str


class OrganizationAssignmentCreate(BaseModel):
    user_id: str
    organization_id: str
    role_id: str | None = None
    status: str = "active"


class OrganizationAssignmentRead(OrganizationAssignmentCreate):
    id: str
