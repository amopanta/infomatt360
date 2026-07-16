"""Pruebas del cache de permisos efectivos (hallazgo E-004 de la auditoria
tecnica de julio 2026, ver docs/108) -- `get_project_permissions` podia
hacer hasta 3 queries por chequeo, sin ningun cache, en practicamente cada
endpoint de escritura.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.api.permissions import get_project_permissions
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.services.permission_cache_service import (
    CachedProjectAssignment,
    RedisPermissionCache,
    get_permission_cache,
    in_memory_permission_cache,
    invalidate_permissions_for_user,
    reset_distributed_permission_cache,
)


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="permcache-project", name="Proyecto")
        template = BuilderTemplate(id="permcache-template", project_id=project.id, name="Plantilla", status="published")
        role = Role(id="permcache-role", name="Capturista", permissions="records.write,records.read")
        user = User(id="permcache-user", full_name="Usuario", document_id="permcache-doc", email="permcache-user@example.com", password_hash=hash_password("User12345!"))
        db.add_all([project, template, role, user])
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


def test_in_memory_cache_returns_none_before_set() -> None:
    in_memory_permission_cache.clear()
    assert in_memory_permission_cache.get("u1", "p1") is None


def test_in_memory_cache_hit_returns_cached_role_and_permissions() -> None:
    in_memory_permission_cache.clear()
    in_memory_permission_cache.set("u1", "p1", "role-1", frozenset({"records.read"}))
    assert in_memory_permission_cache.get("u1", "p1") == ("role-1", frozenset({"records.read"}))
    in_memory_permission_cache.clear()


def test_in_memory_cache_hit_preserves_no_direct_role() -> None:
    """El acceso via "Administrador nacional" (asignacion de organizacion,
    sin fila de proyecto propia, ver docs/101) debe seguir devolviendo
    `role_id=None` tras un hit de cache, igual que antes de cachear."""
    in_memory_permission_cache.clear()
    in_memory_permission_cache.set("u1", "p1", None, frozenset({"records.read"}))
    assert in_memory_permission_cache.get("u1", "p1") == (None, frozenset({"records.read"}))
    in_memory_permission_cache.clear()


def test_in_memory_cache_expires_after_ttl(monkeypatch) -> None:
    in_memory_permission_cache.clear()
    original_ttl = settings.permissions_cache_ttl_seconds
    settings.permissions_cache_ttl_seconds = 60
    try:
        clock = {"now": 1000.0}
        monkeypatch.setattr("app.services.permission_cache_service.time.monotonic", lambda: clock["now"])
        in_memory_permission_cache.set("u1", "p1", "role-1", frozenset({"records.read"}))
        assert in_memory_permission_cache.get("u1", "p1") == ("role-1", frozenset({"records.read"}))
        clock["now"] += 61
        assert in_memory_permission_cache.get("u1", "p1") is None
    finally:
        settings.permissions_cache_ttl_seconds = original_ttl
        in_memory_permission_cache.clear()


def test_in_memory_cache_ttl_zero_disables_caching() -> None:
    in_memory_permission_cache.clear()
    original_ttl = settings.permissions_cache_ttl_seconds
    settings.permissions_cache_ttl_seconds = 0
    try:
        in_memory_permission_cache.set("u1", "p1", "role-1", frozenset({"records.read"}))
        assert in_memory_permission_cache.get("u1", "p1") is None
    finally:
        settings.permissions_cache_ttl_seconds = original_ttl
        in_memory_permission_cache.clear()


def test_invalidate_user_only_clears_that_users_entries() -> None:
    in_memory_permission_cache.clear()
    in_memory_permission_cache.set("u1", "p1", "role-1", frozenset({"records.read"}))
    in_memory_permission_cache.set("u2", "p1", "role-2", frozenset({"records.write"}))
    in_memory_permission_cache.invalidate_user("u1")
    assert in_memory_permission_cache.get("u1", "p1") is None
    assert in_memory_permission_cache.get("u2", "p1") == ("role-2", frozenset({"records.write"}))
    in_memory_permission_cache.clear()


def test_redis_backend_without_url_falls_back_to_memory() -> None:
    original_backend = settings.permissions_cache_backend
    original_redis_url = settings.redis_url
    settings.permissions_cache_backend = "redis"
    settings.redis_url = ""
    reset_distributed_permission_cache()
    try:
        assert get_permission_cache() is in_memory_permission_cache
    finally:
        settings.permissions_cache_backend = original_backend
        settings.redis_url = original_redis_url
        reset_distributed_permission_cache()


def test_redis_permission_cache_key_and_round_trip(monkeypatch) -> None:
    """No requiere un Redis real: se reemplaza el cliente por un stub minimo
    para verificar el formato de clave/serializacion sin depender de infra."""

    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}

        def get(self, key: str) -> str | None:
            return self.store.get(key)

        def setex(self, key: str, ttl: int, value: str) -> None:
            assert ttl > 0
            self.store[key] = value

    cache = RedisPermissionCache.__new__(RedisPermissionCache)
    cache._redis = FakeRedis()  # type: ignore[attr-defined]
    cache._prefix = "infomatt360:permissions"  # type: ignore[attr-defined]

    cache.set("u1", "p1", "role-1", frozenset({"records.read", "records.write"}))
    assert cache._redis.store == {"infomatt360:permissions:u1:p1": "role-1|records.read,records.write"}  # type: ignore[attr-defined]
    assert cache.get("u1", "p1") == ("role-1", frozenset({"records.read", "records.write"}))
    assert cache.get("u1", "p-other") is None

    cache.set("u1", "p2", None, frozenset({"records.read"}))
    assert cache.get("u1", "p2") == (None, frozenset({"records.read"}))


def test_get_project_permissions_hits_cache_on_second_call_without_reflecting_db_only_change() -> None:
    """Prueba que el segundo llamado en verdad usa el cache (no vuelve a
    consultar la BD): se cambia el permiso del rol directo en la BD sin
    invalidar, y el segundo llamado debe seguir devolviendo el valor viejo
    cacheado -- si no hubiera cache, este assert fallaria."""
    engine, sessions = setup_client()
    in_memory_permission_cache.clear()
    try:
        with sessions() as db:
            first_assignment, first_permissions = get_project_permissions(db, "permcache-user", "permcache-project")
            assert first_permissions == set()  # sin asignacion todavia

            db.add(UserProjectAssignment(user_id="permcache-user", project_id="permcache-project", role_id="permcache-role", status="active"))
            db.commit()

            # Sin invalidar: el segundo llamado debe seguir viendo el cache
            # vacio de antes, no la asignacion recien creada por fuera del
            # servicio (que si invalida, ver assignment_service.py).
            _second_assignment, second_permissions = get_project_permissions(db, "permcache-user", "permcache-project")
            assert second_permissions == set()

            invalidate_permissions_for_user("permcache-user")
            third_assignment, third_permissions = get_project_permissions(db, "permcache-user", "permcache-project")
            assert third_permissions == {"records.write", "records.read"}
            assert third_assignment is not None and third_assignment.role_id == "permcache-role"

            # Un cuarto llamado (cache hit sobre la asignacion recien
            # invalidada/recalculada) debe seguir exponiendo el mismo
            # `role_id` -- regresion del bug real encontrado en
            # `approval_flow_service.user_can_execute_step`, que compara
            # `assignment.role_id` y con un hit de cache mal hecho recibia
            # `None` incondicionalmente (ver docs/108).
            fourth_assignment, fourth_permissions = get_project_permissions(db, "permcache-user", "permcache-project")
            assert fourth_permissions == {"records.write", "records.read"}
            assert isinstance(fourth_assignment, CachedProjectAssignment)
            assert fourth_assignment.role_id == "permcache-role"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        in_memory_permission_cache.clear()


def test_creating_assignment_invalidates_cache_so_user_gets_access_immediately() -> None:
    """Regresion end-to-end de E-004: sin invalidar al crear una asignacion,
    un usuario que fue denegado justo antes seguiria denegado hasta que
    expire el TTL, aunque el administrador ya le haya dado acceso."""
    engine, sessions = setup_client()
    in_memory_permission_cache.clear()
    try:
        with sessions() as db:
            admin_role = Role(id="permcache-admin-role", name="Admin", permissions="identity.users.manage")
            admin = User(id="permcache-admin", full_name="Admin", document_id="permcache-admin-doc", email="permcache-admin@example.com", password_hash=hash_password("Admin12345!"))
            db.add_all([
                admin_role, admin,
                UserProjectAssignment(user_id=admin.id, project_id="permcache-project", role_id="permcache-admin-role", status="active"),
            ])
            db.commit()

        with TestClient(app) as client:
            user_headers = auth(client, "permcache-user@example.com", "User12345!")
            denied = client.post(
                "/api/v1/runtime/save", headers=user_headers,
                json={"project_id": "permcache-project", "template_id": "permcache-template", "values": []},
            )
            assert denied.status_code == 403

            admin_headers = auth(client, "permcache-admin@example.com", "Admin12345!")
            assign_response = client.post(
                "/api/v1/assignments/", headers=admin_headers,
                json={"user_id": "permcache-user", "project_id": "permcache-project", "role_id": "permcache-role"},
            )
            assert assign_response.status_code == 200, assign_response.text

            allowed = client.post(
                "/api/v1/runtime/save", headers=user_headers,
                json={"project_id": "permcache-project", "template_id": "permcache-template", "values": []},
            )
            assert allowed.status_code == 200, allowed.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        in_memory_permission_cache.clear()
