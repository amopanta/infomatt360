from app.db.base import Base
from app.db.session import engine
from app.models import acta, assignment, backup, enrollment, excel_import, identity, installation, organization  # noqa: F401
from sqlalchemy import inspect, text


def init_db() -> None:
    if inspect(engine).has_table("alembic_version"):
        _ensure_local_compat_columns()
        return
    Base.metadata.create_all(bind=engine)
    _ensure_local_compat_columns()


def _ensure_local_compat_columns() -> None:
    """Agrega columnas nuevas en bases locales creadas antes de las migraciones.

    Produccion debe usar Alembic; esto mantiene funcionales las demos SQLite y
    entornos MVP donde `create_all` no altera tablas ya existentes.
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []

    if "approval_flows" in table_names:
        flow_columns = {column["name"] for column in inspector.get_columns("approval_flows")}
        if "flow_version" not in flow_columns:
            statements.append("ALTER TABLE approval_flows ADD COLUMN flow_version INTEGER NOT NULL DEFAULT 1")

    if "review_actions" in table_names:
        review_columns = {column["name"] for column in inspector.get_columns("review_actions")}
        if "approval_flow_id" not in review_columns:
            statements.append("ALTER TABLE review_actions ADD COLUMN approval_flow_id VARCHAR(36)")
        if "approval_flow_version" not in review_columns:
            statements.append("ALTER TABLE review_actions ADD COLUMN approval_flow_version INTEGER")

    if "runtime_records" in table_names:
        runtime_columns = {column["name"] for column in inspector.get_columns("runtime_records")}
        if "approval_flow_id" not in runtime_columns:
            statements.append("ALTER TABLE runtime_records ADD COLUMN approval_flow_id VARCHAR(36)")
        if "approval_flow_version" not in runtime_columns:
            statements.append("ALTER TABLE runtime_records ADD COLUMN approval_flow_version VARCHAR(20)")
        if "approval_flow_snapshot_json" not in runtime_columns:
            statements.append("ALTER TABLE runtime_records ADD COLUMN approval_flow_snapshot_json TEXT")

    if "builder_templates" in table_names:
        builder_columns = {column["name"] for column in inspector.get_columns("builder_templates")}
        if "theme_json" not in builder_columns:
            statements.append("ALTER TABLE builder_templates ADD COLUMN theme_json TEXT")

    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
