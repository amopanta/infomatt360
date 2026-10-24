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
    # Usuario y contraseña del SMTP (docs/151): se guardan en la configuración
    # del asistente, no en la base de datos.
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=256)
    use_tls: bool = True


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


class InstallCodeRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=40)


class InstallCodeResponse(BaseModel):
    valid: bool
    kind: str  # "setup" (sin instalar) | "recovery" (ya instalado)


class InstallDatabaseRequest(BaseModel):
    """Base externa PostgreSQL. «bundled» vuelve a la base incluida."""

    mode: str = Field(default="external", pattern="^(bundled|external)$")
    host: str = Field(default="", max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = Field(default="", max_length=120)
    username: str = Field(default="", max_length=120)
    password: str = Field(default="", max_length=256)
    sslmode: str | None = Field(default=None, pattern="^(disable|prefer|require|verify-full)$")


class InstallDatabaseResponse(BaseModel):
    mode: str
    server_version: str | None = None
    empty: bool | None = None
    current_revision: str | None = None
    usable: bool = True
    foreign_tables: list[str] = []
    restarting: bool = False


class InstallMailRequest(BaseModel):
    host: str = Field(..., min_length=3, max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="", max_length=255)
    password: str = Field(default="", max_length=256)
    use_tls: bool = True
    sender_email: EmailStr
    test_recipient: EmailStr | None = None


class InstallRecoverAdminRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=180)
    document_id: str = Field(default="", max_length=50)
    password: str = Field(..., min_length=10, max_length=128)


class InstallRecoverAdminResponse(BaseModel):
    created: bool
    email: str
    projects: list[str]


class InstallBootstrapResponse(BaseModel):
    organization_id: str
    project_id: str
    role_id: str
    user_id: str
    mail_profile_id: str | None = None
    storage_profile_id: str | None = None
    scheduled_task_id: str | None = None
