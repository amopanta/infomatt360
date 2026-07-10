from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, User


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="participant-project", name="Proyecto Participantes")
        user = User(id="participant-user", full_name="Gestor", document_id="participant-user-doc", email="participant-user@example.com", password_hash=hash_password("Gestor12345!"))
        db.add_all([
            project,
            user,
            UserProjectAssignment(user_id=user.id, project_id=project.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_participant_creation_blocks_duplicate_document_in_same_project():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "participant-user@example.com", "Gestor12345!")

            first = client.post(
                "/api/v1/participants/",
                headers=headers,
                json={"project_id": "participant-project", "document_id": "CC-1", "full_name": "Ana Gomez"},
            )
            assert first.status_code == 200
            assert first.json()["duplicate_flag"] == "none"

            duplicate = client.post(
                "/api/v1/participants/",
                headers=headers,
                json={"project_id": "participant-project", "document_id": "CC-1", "full_name": "Otro nombre, mismo documento"},
            )
            assert duplicate.status_code == 409

            without_document = client.post(
                "/api/v1/participants/",
                headers=headers,
                json={"project_id": "participant-project", "full_name": "Sin documento"},
            )
            assert without_document.status_code == 200
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
