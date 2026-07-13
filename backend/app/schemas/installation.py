from pydantic import BaseModel, EmailStr, Field


class InstallStatusResponse(BaseModel):
    installed: bool
    installer_enforced: bool


class InstallRequirementCheck(BaseModel):
    key: str
    label: str
    status: str  # "ok" | "warning" | "error"
    detail: str | None = None


class InstallRequirementsResponse(BaseModel):
    ready: bool
    checks: list[InstallRequirementCheck]


class InstallMailSetup(BaseModel):
    """Datos minimos para dejar un MailProfile activo desde el instalador.

    Paso opcional: si se omite, el correo se configura despues en
    /admin/mail-profiles, igual que hoy.
    """

    sender_email: EmailStr
    server_host: str | None = None
    server_port: str | None = None


class InstallStorageSetup(BaseModel):
    """Paso opcional: siempre crea un perfil local por defecto.

    Conectores en la nube (S3/MinIO/Google Drive) requieren credenciales y
    un flujo OAuth que ya tiene pantalla propia en /admin/storage -- no se
    duplica aqui, el wizard solo deja listo el almacenamiento local minimo
    para operar desde el primer dia.
    """

    max_file_size_mb: int = Field(default=25, ge=1, le=1000)


class InstallBackupSetup(BaseModel):
    """Paso opcional: crea una ScheduledTask (task_type=backup) recurrente."""

    frequency: str = Field(default="daily", pattern="^(hourly|daily|weekly)$")


class InstallBootstrapRequest(BaseModel):
    organization_name: str = Field(..., min_length=2)
    organization_slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    organization_public_url: str | None = Field(default=None, max_length=300)
    project_name: str = Field(..., min_length=3)
    admin_full_name: str = Field(..., min_length=3)
    admin_document_id: str = Field(..., min_length=5)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=10)
    mail: InstallMailSetup | None = None
    storage: InstallStorageSetup | None = None
    backup: InstallBackupSetup | None = None


class InstallBootstrapResponse(BaseModel):
    organization_id: str
    project_id: str
    role_id: str
    user_id: str
    mail_profile_id: str | None = None
    storage_profile_id: str | None = None
    scheduled_task_id: str | None = None
