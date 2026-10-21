"""H11: barrido de ESCRITURA entre proyectos.

Mismo escenario que test_cross_project_access_scan: un usuario con todos los
permisos en A (salvo el de plataforma) llama cada POST/PUT/PATCH/DELETE con
un cuerpo válido generado del esquema OpenAPI y apuntando a datos de B. Al
final de cada llamada se compara una foto de las filas de B: ningún cambio
en B está permitido.
"""

import json
import re

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from test_cross_project_access_scan import B_IDS, _seed

B_VALUES = set(B_IDS.values()) | {"obs-b", "proj-b", "org-b", "user-b", "col-b", "cmp-b", "val-b", "evt-b", "layer-b", "feat-b", "dev-b", "pt-b", "device-b"}
# Acciones del propio usuario o de plataforma, no de un proyecto: no pueden tocar B por diseño.
SKIP_PREFIXES = ("/api/v1/auth/", "/api/v1/install/", "/api/v1/public")


def _resolve(schema: dict, spec: dict) -> dict:
    while "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return schema


def _example(schema: dict, spec: dict, name: str = "", depth: int = 0):
    schema = _resolve(schema, spec)
    if depth > 4:
        return None
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [s for s in schema[key] if _resolve(s, spec).get("type") != "null"] or schema[key]
            return _example(options[0], spec, name, depth + 1)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        props = schema.get("properties", {})
        return {key: _example(value, spec, key, depth + 1) for key, value in props.items()}
    if kind == "array":
        return [_example(schema.get("items", {}), spec, name, depth + 1)]
    if kind == "integer":
        return max(1, schema.get("minimum", 1))
    if kind == "number":
        return max(1.0, schema.get("minimum", 1.0))
    if kind == "boolean":
        return False
    # Texto: identificadores de B donde corresponde
    if name in B_IDS:
        return B_IDS[name]
    if name.endswith("_id"):
        return {"user_id": "user-b", "layer_id": "layer-b", "column_id": "col-b", "component_id": "cmp-b"}.get(name, "proj-b")
    if schema.get("format") == "date-time":
        return "2026-01-01T00:00:00Z"
    if schema.get("format") == "email" or name == "email":
        return "otro@example.com"
    return "x" * max(1, schema.get("minLength", 1)) if schema.get("minLength", 0) > 1 else "SECRETO-B-escrito"


def _snapshot(engine) -> dict[str, list]:
    """Filas que pertenecen a B (por project_id/organization_id o por id conocido)."""
    out: dict[str, list] = {}
    with engine.connect() as conn:
        for table in inspect(engine).get_table_names():
            columns = [c["name"] for c in inspect(engine).get_columns(table)]
            rows = conn.execute(text(f'SELECT * FROM "{table}"')).mappings().all()
            mine = [dict(r) for r in rows if any(str(r.get(c)) in B_VALUES for c in ("id", "project_id", "organization_id", "template_id", "record_id", "participant_id", "case_id", "team_id") if c in columns)]
            # updated_at/last_* cambian con lecturas inocuas en algunos servicios
            out[table] = sorted(json.dumps({k: v for k, v in r.items() if not str(k).startswith(("last_", "updated_at"))}, default=str, sort_keys=True) for r in mine)
    return out


def scan_writes(email: str = "a@example.com") -> list[str]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        _seed(db)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    findings: list[str] = []
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            token = client.post("/api/v1/auth/login", json={"email": email, "password": "Clave12345!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            spec = app.openapi()
            for path, operations in sorted(spec["paths"].items()):
                if path.startswith(SKIP_PREFIXES):
                    continue
                for method in ("post", "put", "patch", "delete"):
                    op = operations.get(method)
                    if not op:
                        continue
                    url = re.sub(r"{(\w+)}", lambda m: B_IDS.get(m.group(1), "x-b"), path)
                    params = {p["name"]: B_IDS.get(p["name"], "proj-b" if p["name"].endswith("_id") else "x")
                              for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
                    kwargs: dict = {"params": params}
                    content = op.get("requestBody", {}).get("content", {})
                    if "application/json" in content:
                        kwargs["json"] = _example(content["application/json"]["schema"], spec)
                    elif "multipart/form-data" in content or "application/x-www-form-urlencoded" in content:
                        schema = _resolve((content.get("multipart/form-data") or content["application/x-www-form-urlencoded"])["schema"], spec)
                        data, files = {}, {}
                        for key, prop in schema.get("properties", {}).items():
                            resolved = _resolve(prop, spec)
                            if resolved.get("format") == "binary" or resolved.get("contentMediaType"):
                                files[key] = ("prueba.csv", b"a,b\n1,2\n", "text/csv")
                            else:
                                value = _example(prop, spec, key)
                                data[key] = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                        kwargs.update(data=data, files=files or None)
                    before = _snapshot(engine)
                    response = client.request(method.upper(), url, headers=headers, **kwargs)
                    if _snapshot(engine) != before:
                        findings.append(f"{response.status_code} {method.upper()} {path}")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
    return findings


def test_write_scan_detects_changes_when_access_is_legit():
    """Control positivo: el dueño de B sí modifica sus datos con los mismos cuerpos."""
    assert len(scan_writes("b@example.com")) >= 15


def test_no_write_route_changes_another_projects_data():
    findings = scan_writes()
    assert findings == [], "Rutas que modifican datos de otro proyecto:\n" + "\n".join(findings)


def test_project_admin_cannot_grant_more_than_they_have_or_assign_elsewhere():
    from app.models.identity import Role
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        _seed(db)
        db.add(Role(id="role-platform", name="Plataforma", permissions="organizations.manage,records.read"))
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            token = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "Clave12345!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            # A otro proyecto: no (antes sí, incluso a uno mismo)
            assert client.post("/api/v1/assignments/", headers=headers, json={"user_id": "user-a", "project_id": "proj-b", "role_id": "role-all"}).status_code == 403
            # Rol con más permisos que los propios: no
            assert client.post("/api/v1/assignments/", headers=headers, json={"user_id": "user-b", "project_id": "proj-a", "role_id": "role-platform"}).status_code == 403
            # Mismo proyecto y rol que uno ya tiene: sí
            assert client.post("/api/v1/assignments/", headers=headers, json={"user_id": "user-b", "project_id": "proj-a", "role_id": "role-all"}).status_code == 200
            # Listar: solo proyectos que administra
            assert client.get("/api/v1/assignments/", headers=headers, params={"project_id": "proj-b"}).status_code == 403
            assert {row["project_id"] for row in client.get("/api/v1/assignments/", headers=headers).json()} == {"proj-a"}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
