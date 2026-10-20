from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.auth import validate_bcrypt_password
from app.schemas.identity import UserCreate


class CurrentUserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    status: str
    allowed_channels: list[str]


class AdminUserRead(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    status: str
    must_change_password: bool
    mfa_enabled: bool
    role_id: str | None = None
    role_name: str | None = None
    assignment_status: str = "active"
    permissions: list[str] = Field(default_factory=list)
    inherited_permissions: list[str] = Field(default_factory=list)


class AdminProjectUserCreate(UserCreate):
    role_id: str
    admin_password: str = Field(..., min_length=6, max_length=128)
    _password_fits_bcrypt = field_validator("admin_password")(validate_bcrypt_password)


class AdminProjectUserCreated(BaseModel):
    user: AdminUserRead
    temporary_password: str


class AdminProjectAccessUpdate(BaseModel):
    role_id: str
    assignment_status: Literal["active", "suspended"]
    admin_password: str = Field(..., min_length=6, max_length=128)
    _password_fits_bcrypt = field_validator("admin_password")(validate_bcrypt_password)


class AdminProjectRoleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    permissions: list[str] = Field(..., min_length=1)
    admin_password: str = Field(..., min_length=6, max_length=128)
    _password_fits_bcrypt = field_validator("admin_password")(validate_bcrypt_password)


class AdminEmailUpdate(BaseModel):
    email: EmailStr
    admin_password: str = Field(..., min_length=6, max_length=128)

    _admin_password_fits_bcrypt = field_validator("admin_password")(
        validate_bcrypt_password
    )


class AdminPasswordReset(BaseModel):
    admin_password: str = Field(..., min_length=6, max_length=128)
    temporary_password: str | None = Field(None, min_length=15, max_length=128)

    _passwords_fit_bcrypt = field_validator("admin_password", "temporary_password")(
        validate_bcrypt_password
    )


class AdminPasswordResetResponse(BaseModel):
    message: str
    temporary_password: str | None = None


class AdminMfaReset(BaseModel):
    admin_password: str = Field(..., min_length=6, max_length=128)
    _admin_password_fits_bcrypt = field_validator("admin_password")(
        validate_bcrypt_password
    )
