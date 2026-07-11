from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def validate_bcrypt_password(value: str | None) -> str | None:
    if value is None:
        return value
    if len(value.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    device_fingerprint: str | None = None

    _password_fits_bcrypt = field_validator("password")(validate_bcrypt_password)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_challenge_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=256)


class MfaSetupRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    _password_fits_bcrypt = field_validator("current_password")(validate_bcrypt_password)


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=64)


class MfaConfirmResponse(BaseModel):
    message: str
    recovery_codes: list[str]


class MfaVerifyRequest(BaseModel):
    challenge_token: str = Field(..., min_length=32)
    code: str = Field(..., min_length=6, max_length=64)
    device_fingerprint: str | None = None


class MfaDisableRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    code: str = Field(..., min_length=6, max_length=64)
    _password_fits_bcrypt = field_validator("current_password")(validate_bcrypt_password)


class MfaStatusResponse(BaseModel):
    enabled: bool
    recovery_codes_remaining: int


class SessionProject(BaseModel):
    id: str
    name: str
    role_id: str | None = None
    permissions: list[str] = []


class SessionResponse(BaseModel):
    user_id: str
    full_name: str
    email: EmailStr
    must_change_password: bool = False
    projects: list[SessionProject] = []


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=15, max_length=128)
    confirm_password: str = Field(..., min_length=15, max_length=128)

    _passwords_fit_bcrypt = field_validator(
        "current_password", "new_password", "confirm_password"
    )(validate_bcrypt_password)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Las contraseñas no coinciden")
        if self.current_password == self.new_password:
            raise ValueError("La nueva contraseña debe ser diferente")
        return self


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str = "Si la cuenta existe, enviaremos instrucciones de recuperación."


class PasswordResetRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=256)
    new_password: str = Field(..., min_length=15, max_length=128)
    confirm_password: str = Field(..., min_length=15, max_length=128)

    _passwords_fit_bcrypt = field_validator("new_password", "confirm_password")(
        validate_bcrypt_password
    )

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Las contraseñas no coinciden")
        return self


class PasswordOperationResponse(BaseModel):
    message: str
