from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import ALL_PERMISSIONS, GIS_READ, MESSAGES_READ, PROJECT_READ, RECORDS_READ, REPORTS_EXPORT
from app.core.security import hash_password
from app.core.time import utc_now
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User
from app.models.installation import InstallationState
from app.models.messages import MailProfile
from app.models.organization import Organization
from app.models.scheduler import ScheduledTask
from app.models.storage import StorageProfile
from app.schemas.installation import (
    InstallBootstrapRequest,
    InstallBootstrapResponse,
    InstallRequirementCheck,
    InstallRequirementsResponse,
    InstallStatusResponse,
)


class InstallationService:
    def is_installed(self, db: Session) -> bool:
        if not settings.installer_enforced:
            return True
        row = db.query(InstallationState).first()
        return bool(row and row.is_installed)

    def status(self, db: Session) -> InstallStatusResponse:
        return InstallStatusResponse(installed=self.is_installed(db), installer_enforced=settings.installer_enforced)

    def requirements(self, db: Session) -> InstallRequirementsResponse:
        """Verifica los requisitos minimos del servidor antes de instalar.

        Reutiliza las mismas comprobaciones de `/api/v1/health/ready`
        (conexion a la base de datos ya configurada via DATABASE_URL, y el
        directorio de subida de archivos), expuestas aqui bajo
        `/api/v1/install/*` porque ese es el unico prefijo que el
        `InstallGuardMiddleware` deja pasar antes de completar la
        instalacion.

        No permite reconfigurar la base de datos desde el asistente: el
        motor de SQLAlchemy ya quedo creado con `DATABASE_URL` cuando el
        proceso arranco, asi que "configurar la base de datos" solo puede
        significar verificar la conexion ya existente, no cambiarla en
        caliente (eso exige reiniciar el proceso con otra variable de
        entorno, igual que WordPress/Moodle exigen editar su config antes
        de servir la primera peticion en instalaciones sin panel de
        control).
        """
        checks: list[InstallRequirementCheck] = []

        try:
            db.execute(text("SELECT 1")).scalar_one()
            checks.append(InstallRequirementCheck(key="database", label="Conexion a la base de datos", status="ok"))
        except Exception as exc:  # pragma: no cover - depende de infraestructura real
            checks.append(InstallRequirementCheck(key="database", label="Conexion a la base de datos", status="error", detail=str(exc)))

        upload_path = Path(settings.upload_directory)
        if not upload_path.exists():
            checks.append(InstallRequirementCheck(key="uploads", label="Directorio de archivos", status="error", detail=f"No existe: {settings.upload_directory}"))
        else:
            probe = upload_path / ".infomatt360-healthcheck"
            try:
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                checks.append(InstallRequirementCheck(key="uploads", label="Directorio de archivos", status="ok"))
            except Exception as exc:  # pragma: no cover - depende de permisos del sistema operativo
                checks.append(InstallRequirementCheck(key="uploads", label="Directorio de archivos", status="error", detail=str(exc)))

        if settings.secret_key == "CHANGE_ME_IN_PRODUCTION" or settings.secret_key.startswith("change-this"):
            checks.append(InstallRequirementCheck(key="secret_key", label="Clave secreta (SECRET_KEY)", status="warning", detail="Usa el valor de desarrollo por defecto; cambialo antes de produccion"))
        else:
            checks.append(InstallRequirementCheck(key="secret_key", label="Clave secreta (SECRET_KEY)", status="ok"))

        if settings.environment.lower() in {"production", "prod"} and settings.database_url.startswith("sqlite"):
            checks.append(InstallRequirementCheck(key="database_engine", label="Motor de base de datos", status="warning", detail="SQLite no se recomienda como base principal en produccion"))
        else:
            checks.append(InstallRequirementCheck(key="database_engine", label="Motor de base de datos", status="ok"))

        ready = all(check.status != "error" for check in checks)
        return InstallRequirementsResponse(ready=ready, checks=checks)

    def bootstrap(self, db: Session, payload: InstallBootstrapRequest) -> InstallBootstrapResponse:
        if self.is_installed(db):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El sistema ya esta instalado")
        if db.query(Organization).filter(Organization.slug == payload.organization_slug).first() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El slug de organizacion ya existe")

        organization = Organization(
            name=payload.organization_name,
            slug=payload.organization_slug,
            public_url=payload.organization_public_url,
            status="active",
        )
        db.add(organization)
        db.flush()

        project = Project(name=payload.project_name, organization_id=organization.id, status="active")
        db.add(project)
        db.flush()

        admin_role = Role(name="Administrador", description="Rol inicial con todos los permisos del catalogo", permissions=",".join(sorted(ALL_PERMISSIONS)))
        db.add(admin_role)

        # Rol predefinido de solo lectura (ver docs/101 -- jerarquia de
        # roles §21 del Documento Maestro de Requerimientos): disponible
        # desde el arranque de toda organizacion nueva, sin que un admin
        # tenga que ensamblar la lista de permisos a mano.
        auditor_permissions = {PROJECT_READ, RECORDS_READ, GIS_READ, MESSAGES_READ, REPORTS_EXPORT}
        auditor_role = Role(name="Auditor/Consulta", description="Rol de solo lectura: ver proyectos, registros, mapas y mensajes, y exportar reportes.", permissions=",".join(sorted(auditor_permissions)))
        db.add(auditor_role)
        db.flush()

        admin_user = User(
            full_name=payload.admin_full_name,
            document_id=payload.admin_document_id,
            email=str(payload.admin_email),
            password_hash=hash_password(payload.admin_password),
            status="active",
        )
        db.add(admin_user)
        db.flush()

        db.add(UserProjectAssignment(user_id=admin_user.id, project_id=project.id, role_id=admin_role.id, status="active"))

        mail_profile_id: str | None = None
        if payload.mail is not None:
            mail_profile = MailProfile(
                project_id=project.id,
                name="Correo principal",
                provider="smtp",
                sender_email=str(payload.mail.sender_email),
                server_host=payload.mail.server_host,
                server_port=payload.mail.server_port,
                is_default="true",
                status="active",
            )
            db.add(mail_profile)
            db.flush()
            mail_profile_id = mail_profile.id

        storage_profile_id: str | None = None
        if payload.storage is not None:
            storage_profile = StorageProfile(
                project_id=project.id,
                name="Almacenamiento local",
                provider="local",
                max_file_size_mb=payload.storage.max_file_size_mb,
                is_default="true",
                status="active",
            )
            db.add(storage_profile)
            db.flush()
            storage_profile_id = storage_profile.id

        scheduled_task_id: str | None = None
        if payload.backup is not None:
            scheduled_task = ScheduledTask(
                project_id=project.id,
                name="Respaldo automatico",
                task_type="backup",
                target_id=storage_profile_id,
                frequency=payload.backup.frequency,
                status="active",
                next_run_at=utc_now(),
            )
            db.add(scheduled_task)
            db.flush()
            scheduled_task_id = scheduled_task.id

        installation_state = db.query(InstallationState).first()
        if installation_state is None:
            installation_state = InstallationState()
            db.add(installation_state)
        installation_state.is_installed = True
        installation_state.installed_at = utc_now()

        db.commit()
        return InstallBootstrapResponse(
            organization_id=organization.id,
            project_id=project.id,
            role_id=admin_role.id,
            user_id=admin_user.id,
            mail_profile_id=mail_profile_id,
            storage_profile_id=storage_profile_id,
            scheduled_task_id=scheduled_task_id,
        )


installation_service = InstallationService()
