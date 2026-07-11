"""Carga datos demo idempotentes para validar el MVP localmente."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.builder import BuilderComponent, BuilderTemplate, BuilderVersion
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.models.files import FileAsset
from app.models.gis import GisFeature, GisLayer
from app.models.identity import Project, Role, User
from app.models.messages import InternalMessage
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue

DEMO_PROJECT_ID = "demo-project-infomatt360"
DEMO_ROLE_ID = "demo-admin-role"
DEMO_USER_ID = "demo-admin-user"
DEMO_TEMPLATE_ID = "demo-template-characterization"
DEMO_VERSION_ID = "demo-template-version-1"
DEMO_PASSWORD = "Demo12345!"
DEMO_EMAIL = "admin@infomatt360.demo"


def seed(db: Session) -> dict[str, str]:
    """Inserta o actualiza datos demo sin duplicar filas conocidas."""
    role = upsert(
        db,
        Role,
        DEMO_ROLE_ID,
        name="Administrador demo",
        description="Rol demo con permisos amplios para validar el MVP.",
        permissions="projects.read,users.admin,identity.users.manage,records.read,records.write,records.review,records.coordinate,records.approve,reports.export,gis.read,builder.write,messages.write,messages.read,integrations.api_keys.manage,organizations.manage,organizations.branding.manage,backups.manage",
    )
    project = upsert(
        db,
        Project,
        DEMO_PROJECT_ID,
        name="Proyecto Demo InfoMatt360",
        description="Proyecto de demostracion con formularios, registros, reportes y mapas.",
        status="active",
    )
    user = upsert(
        db,
        User,
        DEMO_USER_ID,
        full_name="Administrador Demo",
        document_id="DEMO-ADMIN",
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        phone="3000000000",
        status="active",
        must_change_password=False,
        mfa_enabled=False,
    )
    upsert(db, UserProjectAssignment, "demo-admin-assignment", user_id=user.id, project_id=project.id, role_id=role.id, status="active")
    template = upsert(
        db,
        BuilderTemplate,
        DEMO_TEMPLATE_ID,
        project_id=project.id,
        name="Caracterizacion demo",
        description="Formulario demo para capturar hogar, ubicacion y observaciones.",
        status="published",
    )
    page = upsert(db, BuilderPage, "demo-page-general", template_id=template.id, title="Datos generales", description="Informacion basica", sort_order=1, visible="true")
    section = upsert(db, BuilderSection, "demo-section-household", page_id=page.id, title="Hogar", description="Datos principales del hogar", sort_order=1, visible="true", collapsible="false")
    row = upsert(db, BuilderRow, "demo-row-household", section_id=section.id, sort_order=1, responsive="true")
    column_left = upsert(db, BuilderColumn, "demo-column-left", row_id=row.id, desktop_width=6, tablet_width=12, mobile_width=12, sort_order=1)
    column_right = upsert(db, BuilderColumn, "demo-column-right", row_id=row.id, desktop_width=6, tablet_width=12, mobile_width=12, sort_order=2)
    components = [
        ("demo-component-name", column_left.id, "TEXT", "nombre", "Nombre del hogar", 1, None),
        ("demo-component-members", column_left.id, "NUMBER", "integrantes", "Numero de integrantes", 2, None),
        ("demo-component-location", column_right.id, "GPS", "ubicacion", "Ubicacion", 3, None),
        ("demo-component-notes", column_right.id, "TEXTAREA", "observaciones", "Observaciones", 4, None),
    ]
    for component_id, column_id, component_type, name, label, sort_order, config_json in components:
        upsert(db, BuilderComponent, component_id, template_id=template.id, column_id=column_id, component_type=component_type, name=name, label=label, sort_order=sort_order, config_json=config_json)
    upsert(
        db,
        BuilderVersion,
        DEMO_VERSION_ID,
        template_id=template.id,
        version_number=1,
        schema_json=json.dumps({"template_id": template.id, "name": template.name, "demo": True}, ensure_ascii=False),
        status="published",
    )
    upsert(db, GisLayer, "demo-layer-field", project_id=project.id, name="Visitas demo", layer_type="points", status="active", style_json='{"color":"#0066cc"}')
    records = [
        ("demo-record-001", "submitted", "Hogar Norte", 4, [-74.0721, 4.7110], "Registro demo con coordenada norte."),
        ("demo-record-002", "approved", "Hogar Centro", 3, [-74.0817, 4.6097], "Registro demo aprobado."),
        ("demo-record-003", "submitted", "Hogar Sur", 5, [-74.1009, 4.5709], "Registro demo con seguimiento pendiente."),
    ]
    for record_id, status, name, members, coordinate, notes in records:
        upsert(db, RuntimeRecord, record_id, project_id=project.id, template_id=template.id, version_id=DEMO_VERSION_ID, status=status, submitted_by=user.id)
        values = [
            (f"{record_id}-nombre", "nombre", json.dumps(name, ensure_ascii=False)),
            (f"{record_id}-integrantes", "integrantes", json.dumps(members)),
            (f"{record_id}-ubicacion", "ubicacion", json.dumps({"type": "Point", "coordinates": coordinate})),
            (f"{record_id}-observaciones", "observaciones", json.dumps(notes, ensure_ascii=False)),
        ]
        for value_id, field_name, field_value_json in values:
            upsert(db, RuntimeRecordValue, value_id, record_id=record_id, field_name=field_name, field_value_json=field_value_json)
    upsert(db, GisFeature, "demo-manual-feature", project_id=project.id, layer_id="demo-layer-field", record_id="demo-record-001", feature_type="Point", latitude="4.7110", longitude="-74.0721", status="active")
    upsert(db, FileAsset, "demo-file-001", project_id=project.id, record_id="demo-record-001", asset_type="image", original_name="foto-demo.jpg", storage_path="uploads/demo/foto-demo.jpg", size_bytes=204800, metadata_json='{"demo":true}')
    upsert(db, InternalMessage, "demo-message-001", project_id=project.id, sender_id=user.id, recipient_id=user.id, subject="Bienvenido a Mensajes", body="Mensaje demo para validar la bandeja interna del proyecto.", status="unread")
    db.add(AuditLog(user_id=user.id, project_id=project.id, module="seed", action="demo_seed", entity_type="project", entity_id=project.id, after_json='{"source":"seed_demo"}'))
    db.commit()
    return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "project_id": DEMO_PROJECT_ID}


def upsert(db: Session, model: type, object_id: str, **values):
    row = db.get(model, object_id)
    if row is None:
        row = model(id=object_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        credentials = seed(db)
    print("Datos demo listos")
    print(f"Usuario: {credentials['email']}")
    print(f"Clave: {credentials['password']}")
    print(f"Proyecto: {credentials['project_id']}")


if __name__ == "__main__":
    main()
