from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cli.seed_demo import DEMO_EMAIL, DEMO_PROJECT_ID, DEMO_ROLE_ID, DEMO_USER_ID, seed
from app.db.base import Base
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord


def test_seed_demo_is_idempotent_and_creates_operational_data():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        first = seed(db)
        second = seed(db)

        assert first == second
        assert first["email"] == DEMO_EMAIL
        assert first["project_id"] == DEMO_PROJECT_ID
        assert db.get(User, DEMO_USER_ID).email == DEMO_EMAIL
        assert db.get(Project, DEMO_PROJECT_ID).status == "active"
        permissions = set(db.get(Role, DEMO_ROLE_ID).permissions.split(","))
        assert "identity.users.manage" in permissions
        assert "records.write" in permissions
        assert "integrations.api_keys.manage" in permissions
        assert db.query(UserProjectAssignment).filter_by(user_id=DEMO_USER_ID, project_id=DEMO_PROJECT_ID, status="active").count() == 1
        assert db.query(BuilderTemplate).filter_by(project_id=DEMO_PROJECT_ID, status="published").count() == 1
        assert db.query(RuntimeRecord).filter_by(project_id=DEMO_PROJECT_ID).count() == 3

    Base.metadata.drop_all(bind=engine)
