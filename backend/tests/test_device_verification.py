"""A device proof is user-bound, field-bound, short-lived and single-use."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.api.v1 import device_verification as api
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.device_verification import DeviceCredential
from app.models.identity import Project, Role, User
from app.schemas.runtime_record import RuntimeValueCreate
from app.services.runtime_record_service import runtime_record_service


@pytest.fixture
def database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        db.add_all([
            Project(id="device-project", name="Device test"),
            Role(id="device-role", name="Gestor", permissions="records.write"),
            User(id="device-user", full_name="Gestor", document_id="device-doc", email="device@example.com", password_hash=hash_password("DeviceTest123!")),
            BuilderTemplate(id="device-template", project_id="device-project", name="Formulario", status="draft"),
            BuilderComponent(id="device-field", template_id="device-template", component_type="FINGERPRINT", name="device_check", label="Verificar dispositivo", config_json=json.dumps({"required": True})),
            UserProjectAssignment(user_id="device-user", project_id="device-project", role_id="device-role", status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    yield sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_registration_authentication_and_single_use(database, monkeypatch):
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"email": "device@example.com", "password": "DeviceTest123!"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        request = {"template_id": "device-template", "component_id": "device-field"}

        begin = client.post("/api/v1/device-verification/begin", json=request, headers=headers)
        assert begin.status_code == 200, begin.text
        assert begin.json()["operation"] == "register"
        assert begin.json()["public_key"]["authenticatorSelection"]["authenticatorAttachment"] == "platform"
        assert begin.json()["public_key"]["authenticatorSelection"]["userVerification"] == "required"

        monkeypatch.setattr(api, "verify_registration_response", lambda **kwargs: SimpleNamespace(
            credential_id=b"credential-1", credential_public_key=b"public-key-1", sign_count=0,
        ))
        finish = client.post("/api/v1/device-verification/finish", json={
            "verification_id": begin.json()["verification_id"], "credential": {"id": "fake-registration"},
        }, headers=headers)
        assert finish.status_code == 200, finish.text
        proof = finish.json()
        assert proof["method"] == "device_user_verification"
        with database() as db:
            assert db.query(DeviceCredential).filter_by(user_id="device-user").count() == 1
            runtime_record_service._consume_device_verifications(db, "device-template", [
                RuntimeValueCreate(field_name="device_check", field_value_json=json.dumps(proof)),
            ], "device-user", "record-1", "submitted")
            db.commit()
            with pytest.raises(ValueError, match="ya fue usada"):
                runtime_record_service._consume_device_verifications(db, "device-template", [
                    RuntimeValueCreate(field_name="device_check", field_value_json=json.dumps(proof)),
                ], "device-user", "record-2", "submitted")
            with pytest.raises(ValueError, match="expiró o ya fue usada"):
                runtime_record_service._consume_device_verifications(db, "device-template", [
                    RuntimeValueCreate(field_name="device_check", field_value_json=json.dumps(proof)),
                ], "otro-usuario", "record-3", "submitted")

        begin_again = client.post("/api/v1/device-verification/begin", json=request, headers=headers)
        assert begin_again.status_code == 200
        assert begin_again.json()["operation"] == "authenticate"
        from app.api.v1.device_verification import _encode
        monkeypatch.setattr(api, "verify_authentication_response", lambda **kwargs: SimpleNamespace(new_sign_count=1))
        authenticated = client.post("/api/v1/device-verification/finish", json={
            "verification_id": begin_again.json()["verification_id"],
            "credential": {"id": _encode(b"credential-1")},
        }, headers=headers)
        assert authenticated.status_code == 200, authenticated.text
        assert authenticated.json()["method"] == "device_user_verification"
        with database() as db:
            assert db.query(DeviceCredential).filter_by(user_id="device-user").one().sign_count == 1


def test_unverified_and_missing_proofs_are_rejected(database):
    with database() as db:
        with pytest.raises(ValueError, match="Falta verificar"):
            runtime_record_service._consume_device_verifications(db, "device-template", [], "device-user", "record-1", "submitted")
        with pytest.raises(ValueError, match="expiró o ya fue usada"):
            runtime_record_service._consume_device_verifications(db, "device-template", [
                RuntimeValueCreate(field_name="device_check", field_value_json=json.dumps({"device_verification_id": "made-up", "method": "device_user_verification"})),
            ], "device-user", "record-1", "submitted")
