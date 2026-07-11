"""Verifica el estado offline de la base demo local."""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core.config import settings

REQUIRED_COUNTS = {
    "users": 1,
    "projects": 1,
    "roles": 1,
    "user_project_assignments": 1,
    "builder_templates": 1,
    "builder_components": 1,
    "runtime_records": 1,
    "runtime_record_values": 1,
    "gis_layers": 1,
    "gis_features": 1,
    "file_assets": 1,
    "internal_messages": 1,
    "audit_logs": 1,
}


def expected_heads() -> tuple[str, ...]:
    """Devuelve las revisiones head esperadas segun las migraciones actuales."""
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    return tuple(script.get_heads())


def main() -> None:
    """Imprime resumen y falla si la demo no tiene lo minimo esperado."""
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    )
    failures: list[str] = []
    heads = expected_heads()

    with engine.connect() as conn:
        revision = scalar(conn, "select version_num from alembic_version")
        print(f"DATABASE_URL={settings.database_url}")
        print(f"ALEMBIC_VERSION={revision}")
        print(f"ALEMBIC_HEADS={', '.join(heads)}")
        if revision not in heads:
            failures.append(f"Alembic esperado {'/'.join(heads)}, encontrado {revision}")

        for table, minimum in REQUIRED_COUNTS.items():
            count = int(scalar(conn, f"select count(*) from {table}") or 0)
            print(f"{table}={count}")
            if count < minimum:
                failures.append(f"{table} tiene {count}; minimo esperado {minimum}")

    if failures:
        print("")
        print("Demo DB incompleta:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("")
    print("Demo DB OK.")


def scalar(conn, sql: str):
    return conn.execute(text(sql)).scalar_one_or_none()


if __name__ == "__main__":
    main()
