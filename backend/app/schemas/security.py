from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.auth import validate_bcrypt_password


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
