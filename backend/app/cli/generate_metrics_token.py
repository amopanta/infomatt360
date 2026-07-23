"""CLI para generar un token de scraping para Prometheus (docs/118).

`GET /api/v1/health/metrics/prometheus` exige un JWT valido (`require_metrics_viewer`)
igual que cualquier otro endpoint -- Prometheus no puede iniciar sesion
interactivamente, asi que en vez de agregar un mecanismo de autenticacion
nuevo (y debilitar el endpoint existente) se reusa el JWT que ya exige, con
un usuario de servicio no interactivo y un token de larga duracion.

No existe un permiso dedicado de "solo ver metricas" en el catalogo
(`app/core/permissions.py::METRICS_VIEW_PERMISSIONS`); se usa
`integrations.api_keys.manage` por ser el mas cercano a "cuenta tecnica/de
integracion" entre las 4 opciones disponibles.

El rol se asigna a nivel de Organizacion (mismo patron "Administrador
nacional" de docs/101), no por proyecto, porque las metricas son globales
al proceso, no de un proyecto en particular.

Uso:
    python -m app.cli.generate_metrics_token
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.permissions import INTEGRATIONS_API_KEYS_MANAGE
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.assignment import UserOrganizationAssignment
from app.models.identity import Role, User
from app.models.organization import Organization

SERVICE_EMAIL = "prometheus-metrics@service.infomatt360.local"
SERVICE_DOCUMENT_ID = "service-prometheus-metrics"
ROLE_NAME = "Servicio de metricas (Prometheus)"
TOKEN_VALIDITY_DAYS = 3650


def ensure_metrics_service_user(db: Session) -> User | None:
    """Crea (o reutiliza, de forma idempotente) el usuario de servicio y su
    asignacion de rol a nivel de organizacion. Devuelve None si todavia no
    existe ninguna organizacion activa."""
    organization = (
        db.query(Organization)
        .filter(Organization.status == "active")
        .order_by(Organization.created_at)
        .first()
    )
    if organization is None:
        return None

    user = db.query(User).filter(User.email == SERVICE_EMAIL).first()
    if user is None:
        user = User(
            full_name="Servicio de metricas (Prometheus)",
            document_id=SERVICE_DOCUMENT_ID,
            email=SERVICE_EMAIL,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            status="active",
        )
        db.add(user)
        db.flush()

    role = db.query(Role).filter(Role.name == ROLE_NAME).first()
    if role is None:
        role = Role(
            name=ROLE_NAME,
            description="Cuenta de servicio no interactiva para que Prometheus pueda leer /api/v1/health/metrics/prometheus.",
            permissions=INTEGRATIONS_API_KEYS_MANAGE,
        )
        db.add(role)
        db.flush()

    assignment = (
        db.query(UserOrganizationAssignment)
        .filter(
            UserOrganizationAssignment.user_id == user.id,
            UserOrganizationAssignment.organization_id == organization.id,
        )
        .first()
    )
    if assignment is None:
        db.add(UserOrganizationAssignment(user_id=user.id, organization_id=organization.id, role_id=role.id, status="active"))
    elif assignment.role_id != role.id or assignment.status != "active":
        assignment.role_id = role.id
        assignment.status = "active"

    db.commit()
    db.refresh(user)
    return user


def main() -> int:
    with SessionLocal() as db:
        user = ensure_metrics_service_user(db)
        if user is None:
            print("No hay ninguna organizacion activa todavia -- corre el instalador primero.")
            return 1

        token = create_access_token(subject=user.id, auth_version=user.auth_version, expires_delta=timedelta(days=TOKEN_VALIDITY_DAYS))
        print(token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
