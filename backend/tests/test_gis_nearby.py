from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.gis import GisFeature
from app.models.identity import Project, User

# Plaza de Bolivar, Bogota, y un punto sobre el mismo meridiano a 0.01 grados
# de latitud (~1.112 km, verificable a mano: 0.01 * pi/180 * 6371 = 1.112 km).
CENTER = (4.5981, -74.0761)
NEARBY = (4.6081, -74.0761)


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="nearby-user", full_name="Nearby User", document_id="nearby-doc", email="nearby@example.com", password_hash=hash_password("NearbyPassword123"))
        outsider = User(id="nearby-outsider", full_name="Outsider", document_id="nearby-outsider-doc", email="nearby-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="nearby-project", name="Proyecto cercania")
        db.add_all([
            user,
            outsider,
            project,
            UserProjectAssignment(user_id=user.id, project_id=project.id, status="active"),
            GisFeature(id="feature-center", project_id=project.id, feature_type="Point", latitude=str(CENTER[0]), longitude=str(CENTER[1]), status="active"),
            GisFeature(id="feature-nearby", project_id=project.id, feature_type="Point", latitude=str(NEARBY[0]), longitude=str(NEARBY[1]), status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_nearby_within_radius_returns_both_features():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "nearby@example.com", "NearbyPassword123")
            response = client.get(
                "/api/v1/gis/features/nearby-project/nearby",
                params={"lat": CENTER[0], "lng": CENTER[1], "radius_km": 2},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            ids = {item["id"] for item in response.json()}
            assert ids == {"feature-center", "feature-nearby"}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_nearby_outside_radius_excludes_far_feature():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "nearby@example.com", "NearbyPassword123")
            response = client.get(
                "/api/v1/gis/features/nearby-project/nearby",
                params={"lat": CENTER[0], "lng": CENTER[1], "radius_km": 0.5},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            ids = {item["id"] for item in response.json()}
            assert ids == {"feature-center"}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_nearby_denied_without_project_access():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "nearby-outsider@example.com", "Outsider12345!")
            response = client.get(
                "/api/v1/gis/features/nearby-project/nearby",
                params={"lat": CENTER[0], "lng": CENTER[1], "radius_km": 2},
                headers=headers,
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
