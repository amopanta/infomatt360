import json

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


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="geo-user", full_name="Geo User", document_id="geo-doc", email="geo@example.com", password_hash=hash_password("GeoPassword123"))
        project = Project(id="geo-project", name="Proyecto geo")
        db.add_all([user, project, UserProjectAssignment(user_id=user.id, project_id=project.id, status="active")])
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


def test_create_feature_populates_geom_as_geojson_text_on_sqlite():
    """En SQLite, GisFeature.geom debe caer al mismo string GeoJSON que
    geometry_json -- confirma que el TypeDecorator dialect-aware nunca
    intenta importar geoalchemy2 (que requeriria Postgres) en este camino."""
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "geo@example.com", "GeoPassword123")
            payload = {
                "project_id": "geo-project",
                "feature_type": "Point",
                "latitude": "4.71",
                "longitude": "-74.07",
                "geometry_json": json.dumps({"type": "Point", "coordinates": [-74.07, 4.71]}),
            }
            response = client.post("/api/v1/gis/features", json=payload, headers=headers)
            assert response.status_code == 200, response.text
            feature_id = response.json()["id"]

        with sessions() as db:
            row = db.query(GisFeature).filter(GisFeature.id == feature_id).one()
            assert row.geom is not None
            geom = json.loads(row.geom)
            assert geom == {"type": "Point", "coordinates": [-74.07, 4.71]}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_create_feature_response_shape_unchanged_geom_not_exposed():
    """Regresion: GisFeatureRead sigue exponiendo solo latitude/longitude/
    geometry_json como antes -- geom es un detalle interno de escritura."""
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "geo@example.com", "GeoPassword123")
            payload = {"project_id": "geo-project", "feature_type": "Point", "latitude": "4.71", "longitude": "-74.07"}
            response = client.post("/api/v1/gis/features", json=payload, headers=headers)
            assert response.status_code == 200, response.text
            body = response.json()
            assert "geom" not in body
            assert body["latitude"] == "4.71"
            assert body["longitude"] == "-74.07"

            listed = client.get("/api/v1/gis/features/geo-project", headers=headers)
            assert listed.status_code == 200
            assert listed.json()[0]["latitude"] == "4.71"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_create_feature_without_coordinates_leaves_geom_none():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "geo@example.com", "GeoPassword123")
            payload = {"project_id": "geo-project", "feature_type": "Point"}
            response = client.post("/api/v1/gis/features", json=payload, headers=headers)
            assert response.status_code == 200, response.text
            feature_id = response.json()["id"]

        with sessions() as db:
            row = db.query(GisFeature).filter(GisFeature.id == feature_id).one()
            assert row.geom is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
