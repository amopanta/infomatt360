from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalFlowCreate(BaseModel):
    project_id: str
    template_id: str | None = None
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class ApprovalFlowRead(ApprovalFlowCreate):
    id: str
    flow_version: int = 1
    created_at: datetime | None = None


class ApprovalFlowUpdate(BaseModel):
    template_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class ApprovalFlowStepCreate(BaseModel):
    flow_id: str
    step_order: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=180)
    action_label: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=60)
    status_after: str = Field(min_length=1, max_length=60, pattern="^[a-z0-9_]+$")
    required_permission: str = Field(min_length=1, max_length=120)
    approver_user_id: str | None = None
    approver_role_id: str | None = None
    require_all: bool = False
    status: str = Field(default="active", pattern="^(active|inactive)$")


class ApprovalFlowStepRead(ApprovalFlowStepCreate):
    id: str
    created_at: datetime | None = None


class ApprovalFlowStepUpdate(BaseModel):
    step_order: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    action_label: str | None = Field(default=None, min_length=1, max_length=120)
    action: str | None = Field(default=None, min_length=1, max_length=60)
    status_after: str | None = Field(default=None, min_length=1, max_length=60, pattern="^[a-z0-9_]+$")
    required_permission: str | None = Field(default=None, min_length=1, max_length=120)
    approver_user_id: str | None = None
    approver_role_id: str | None = None
    require_all: bool | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class ApprovalFlowDetail(ApprovalFlowRead):
    steps: list[ApprovalFlowStepRead] = []


class ReviewNextAction(BaseModel):
    label: str
    to_status: str
    action: str
    required_permission: str | None = None
    source: str = "default"


class ReviewApprovalProgress(BaseModel):
    label: str
    to_status: str
    action: str
    required_count: int
    approved_count: int
    pending_count: int
    approved_user_ids: list[str] = []
    pending_user_ids: list[str] = []
    source: str = "configured"


class ReviewFlowSnapshotStep(BaseModel):
    step_order: int
    name: str
    action_label: str
    action: str
    status_after: str
    required_permission: str
    approver_user_id: str | None = None
    approver_role_id: str | None = None
    require_all: bool = False
    status: str = "active"


class ReviewFlowSnapshot(BaseModel):
    flow_id: str | None = None
    flow_version: str | None = None
    name: str | None = None
    template_id: str | None = None
    steps: list[ReviewFlowSnapshotStep] = []


class ReviewFlowComparison(BaseModel):
    has_snapshot: bool
    changed: bool
    differences: list[str] = []
    snapshot: ReviewFlowSnapshot | None = None
    current: ReviewFlowSnapshot | None = None
