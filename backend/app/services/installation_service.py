from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import ALL_PERMISSIONS
from app.core.security import hash_password
from app.core.time import utc_now
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User
from app.models.installation import InstallationState
from app.models.organization import Organization
from app.schemas.installation import InstallBootstrapRequest, InstallBootstrapResponse, InstallStatusResponse


class InstallationService:
    def is_installed(self, db: Session) -> bool:
        if not settings.installer_enforced:
            return True
        row = db.query(InstallationState).first()
        return bool(row and row.is_installed)

    def status(self, db: Session) -> InstallStatusResponse:
        return InstallStatusResponse(installed=self.is_installed(db), installer_enforced=settings.installer_enforced)

    def bootstrap(self, db: Session, payload: InstallBootstrapRequest) -> InstallBootstrapResponse:
        if self.is_installed(db):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El sistema ya esta instalado")
        if db.query(Organization).filter(Organization.slug == payload.organization_slug).first() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El slug de organizacion ya existe")

        organization = Organization(name=payload.organization_name, slug=payload.organization_slug, status="active")
        db.add(organization)
        db.flush()

        project = Project(name=payload.project_name, organization_id=organization.id, status="active")
        db.add(project)
        db.flush()

        admin_role = Role(name="Administrador", description="Rol inicial con todos los permisos del catalogo", permissions=",".join(sorted(ALL_PERMISSIONS)))
        db.add(admin_role)
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
        )


installation_service = InstallationService()
