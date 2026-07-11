from pydantic import BaseModel, EmailStr, Field


class InstallStatusResponse(BaseModel):
    installed: bool
    installer_enforced: bool


class InstallBootstrapRequest(BaseModel):
    organization_name: str = Field(..., min_length=2)
    organization_slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    project_name: str = Field(..., min_length=3)
    admin_full_name: str = Field(..., min_length=3)
    admin_document_id: str = Field(..., min_length=5)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=10)


class InstallBootstrapResponse(BaseModel):
    organization_id: str
    project_id: str
    role_id: str
    user_id: str
