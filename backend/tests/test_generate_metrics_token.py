from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.permissions import require_any_permission
from app.cli.generate_metrics_token import ROLE_NAME, SERVICE_EMAIL, ensure_metrics_service_user
from app.core.config import settings
from app.core.permissions import METRICS_VIEW_PERMISSIONS
from app.core.security import create_access_token
from app.db.base import Base
from app.models.assignment import UserOrganizationAssignment
from app.models.identity import Role, User
from app.models.organization import Organization


def setup_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        db.add(Organization(id="metrics-org", name="Organizacion de prueba", slug="metrics-org", status="active"))
        db.commit()
    return engine, sessions


def test_ensure_metrics_service_user_returns_none_without_an_organization():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        with sessions() as db:
            assert ensure_metrics_service_user(db) is None
    finally:
        Base.metadata.drop_all(bind=engine)


def test_ensure_metrics_service_user_is_idempotent_and_grants_metrics_permission():
    engine, sessions = setup_db()
    try:
        with sessions() as db:
            first = ensure_metrics_service_user(db)
            second = ensure_metrics_service_user(db)

            assert first.id == second.id
            assert first.email == SERVICE_EMAIL
            assert db.query(User).filter(User.email == SERVICE_EMAIL).count() == 1
            assert db.query(Role).filter(Role.name == ROLE_NAME).count() == 1
            assert db.query(UserOrganizationAssignment).filter_by(user_id=first.id, organization_id="metrics-org", status="active").count() == 1

            role = db.query(Role).filter(Role.name == ROLE_NAME).one()
            granted = {item.strip() for item in role.permissions.split(",") if item.strip()}
            assert not granted.isdisjoint(METRICS_VIEW_PERMISSIONS)

            assert require_any_permission(db, first.id, METRICS_VIEW_PERMISSIONS) is None
    finally:
        Base.metadata.drop_all(bind=engine)


def test_generated_token_decodes_to_the_service_user_and_survives_a_long_expiry():
    engine, sessions = setup_db()
    try:
        with sessions() as db:
            user = ensure_metrics_service_user(db)
            from datetime import timedelta

            token = create_access_token(subject=user.id, auth_version=user.auth_version, expires_delta=timedelta(days=3650))
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            assert payload["sub"] == user.id
            assert payload["ver"] == user.auth_version
    finally:
        Base.metadata.drop_all(bind=engine)
