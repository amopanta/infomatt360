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
from app.models.builder import BuilderTemplate
from app.models.gis import GisFeature
from app.models.identity import Project, User
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


def test_gis_project_map_merges_runtime_and_manual_features():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="map-user", full_name="Map User", document_id="map-doc", email="map@example.com", password_hash=hash_password("MapPassword123"))
        project = Project(id="map-project", name="Proyecto mapas")
        other = Project(id="map-other", name="Otro")
        template = BuilderTemplate(id="map-template", project_id=project.id, name="Visita", status="published")
        record = RuntimeRecord(id="map-record", project_id=project.id, template_id=template.id, status="submitted", submitted_by=user.id)
        db.add_all([
            user,
            project,
            other,
            template,
            UserProjectAssignment(user_id=user.id, project_id=project.id, status="active"),
            record,
            RuntimeRecordValue(record_id=record.id, field_name="ubicacion", field_value_json=json.dumps({"type": "Point", "coordinates": [-74.07, 4.71]})),
            RuntimeRecordValue(record_id=record.id, field_name="sin_mapa", field_value_json=json.dumps("texto")),
            GisFeature(id="manual-feature", project_id=project.id, feature_type="Point", latitude="4.72", longitude="-74.08", status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email": "map@example.com", "password": "MapPassword123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            response = client.get("/api/v1/gis/map/map-project", headers=headers)
            forbidden = client.get("/api/v1/gis/map/map-other", headers=headers)

            assert response.status_code == 200
            features = response.json()["features"]
            assert len(features) == 2
            assert {item["source"] for item in features} == {"gis", "runtime"}
            runtime = next(item for item in features if item["source"] == "runtime")
            assert runtime["record_id"] == "map-record"
            assert runtime["template_name"] == "Visita"
            assert runtime["latitude"] == 4.71
            assert runtime["longitude"] == -74.07
            assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
