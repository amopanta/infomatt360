"""Asistente de instalación: código, base de datos, correo y recuperación (docs/151)."""

import json
import os
import threading

import pytest
from starlette.testclient import TestClient

import app.middleware.install_guard as install_guard_module
from app.core import runtime_config
from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.services import install_code_service, install_setup_service
from test_installation import BOOTSTRAP_PAYLOAD, setup_client


@pytest.fixture()
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "runtime_config_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def enforced(monkeypatch):
    engine, sessions = setup_client()
    monkeypatch.setattr(settings, "installer_enforced", True)
    monkeypatch.setattr(install_guard_module, "SessionLocal", sessions)
    yield sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_runtime_config_keeps_only_allowed_keys_and_applies(config_dir):
    runtime_config.save(str(config_dir), {"smtp_host": "smtp.ejemplo.org", "smtp_port": 465})
    raw = json.loads((config_dir / "runtime.json").read_text(encoding="utf-8"))
    raw["secret_key"] = "intento"
    (config_dir / "runtime.json").write_text(json.dumps(raw), encoding="utf-8")
    assert runtime_config.load(str(config_dir)) == {"smtp_host": "smtp.ejemplo.org", "smtp_port": 465}
    with pytest.raises(ValueError):
        runtime_config.save(str(config_dir), {"secret_key": "x"})

    class Target:
        runtime_config_dir = str(config_dir)
        smtp_host = ""
        secret_key = "original"

    target = Target()
    runtime_config.apply(target)
    assert target.smtp_host == "smtp.ejemplo.org" and target.secret_key == "original"
    if os.name != "nt":
        assert (config_dir / "runtime.json").stat().st_mode & 0o777 == 0o600


def test_watcher_fires_when_config_changes(config_dir):
    changed = threading.Event()
    runtime_config.watch_for_changes(str(config_dir), interval_seconds=0.05, on_change=changed.set)
    runtime_config.save(str(config_dir), {"smtp_host": "nuevo"})
    assert changed.wait(2)


def test_install_requires_code_and_code_is_consumed(config_dir, enforced):
    with TestClient(app) as client:
        assert client.get("/api/v1/install/status").json()["installed"] is False
        # Al arrancar sin instalar, el servidor dejó un código en la carpeta.
        assert (config_dir / "install_code.json").exists()
        code = install_code_service.generate("setup")
        assert client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD).status_code == 403
        assert client.post("/api/v1/install/code/verify", json={"code": "AAAA-BBBB-CCCC"}).status_code == 403
        verified = client.post("/api/v1/install/code/verify", json={"code": code.lower().replace("-", "")})
        assert verified.json() == {"valid": True, "kind": "setup"}
        created = client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD, headers={"X-Install-Code": code})
        assert created.status_code == 200, created.text
        assert not (config_dir / "install_code.json").exists()
        # Instalado: los pasos de infraestructura ya no se pueden usar.
        assert client.post("/api/v1/install/database/test", json={"mode": "bundled"}, headers={"X-Install-Code": code}).status_code == 409


def test_database_and_mail_steps(config_dir, enforced, monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context):
            sent["tls"] = True

        def login(self, username, password):
            sent["login"] = username

        def send_message(self, message):
            sent["to"] = message["To"]

    monkeypatch.setattr(install_setup_service.smtplib, "SMTP", FakeSMTP)
    for key in ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_use_tls", "smtp_from_email"):
        monkeypatch.setattr(settings, key, getattr(settings, key))
    with TestClient(app) as client:
        headers = {"X-Install-Code": install_code_service.generate("setup")}
        assert client.post("/api/v1/install/database/test", json={"mode": "bundled"}, headers=headers).json()["mode"] == "bundled"
        missing = client.post("/api/v1/install/database/test", json={"mode": "external", "host": "db.ejemplo.org"}, headers=headers)
        assert missing.status_code == 422
        mail = {"host": "smtp.gmail.com", "port": 587, "username": "envios@ejemplo.org", "password": "clave-app",
                "use_tls": True, "sender_email": "envios@ejemplo.org", "test_recipient": "responsable@ejemplo.org"}
        assert client.post("/api/v1/install/mail/test", json=mail, headers=headers).json() == {"sent": True}
        assert sent == {"server": ("smtp.gmail.com", 587), "tls": True, "login": "envios@ejemplo.org", "to": "responsable@ejemplo.org"}
        assert client.post("/api/v1/install/mail/save", json=mail, headers=headers).status_code == 200
        assert runtime_config.load(str(config_dir))["smtp_password"] == "clave-app"
        assert settings.smtp_host == "smtp.gmail.com"


def test_database_url_escapes_credentials():
    url = install_setup_service.database_url("db.ejemplo.org", 5432, "infomatt", "usuario@x", "p:ss/w%rd", "require")
    assert url == "postgresql+psycopg2://usuario%40x:p%3Ass%2Fw%25rd@db.ejemplo.org:5432/infomatt?sslmode=require"


def test_recover_admin_with_one_time_code(config_dir, enforced):
    with TestClient(app) as client:
        setup = install_code_service.generate("setup")
        assert client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD, headers={"X-Install-Code": setup}).status_code == 200
        body = {"email": "responsable@ejemplo.org", "full_name": "Persona Responsable", "document_id": "1012345678", "password": "Recupera12345"}
        assert client.post("/api/v1/install/recover-admin", json=body).status_code == 403
        code = install_code_service.generate("recovery")
        assert client.post("/api/v1/install/code/verify", json={"code": code}).json()["kind"] == "recovery"
        recovered = client.post("/api/v1/install/recover-admin", json=body, headers={"X-Install-Code": code})
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["created"] is True
        login = client.post("/api/v1/auth/login", json={"email": "responsable@ejemplo.org", "password": "Recupera12345"})
        assert login.status_code == 200
        # El código sirve una sola vez.
        assert client.post("/api/v1/install/recover-admin", json=body, headers={"X-Install-Code": code}).status_code == 403


def test_recovery_code_expires(config_dir):
    code = install_code_service.generate("recovery")
    data = json.loads((config_dir / "install_code.json").read_text(encoding="utf-8"))
    data["expires_at"] = "2000-01-01T00:00:00+00:00"
    (config_dir / "install_code.json").write_text(json.dumps(data), encoding="utf-8")
    assert install_code_service.verify(code, "recovery") is False


def test_existing_users_count_as_installed(monkeypatch):
    """Una base con datos de antes del asistente no se puede «instalar encima»."""
    engine, sessions = setup_client()
    monkeypatch.setattr(settings, "installer_enforced", True)
    monkeypatch.setattr(install_guard_module, "SessionLocal", sessions)
    try:
        from app.models.identity import User
        with sessions() as db:
            db.add(User(email="antes@ejemplo.org", full_name="Usuaria Anterior", document_id="antes-doc", password_hash="x", status="active"))
            db.commit()
        with TestClient(app) as client:
            assert client.get("/api/v1/install/status").json()["installed"] is True
            assert client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD).status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
