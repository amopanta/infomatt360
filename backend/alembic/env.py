"""Entorno de migraciones Alembic para InfoMatt360.

Alembic controla los cambios de esquema de base de datos. Esto es obligatorio
para ambientes productivos, despliegues en VPS y recuperacion ante fallos.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import settings
from app.db.base import Base
from app.models import acta, backup, enrollment, excel_import, identity, installation, organization  # noqa: F401 registra modelos en metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones sin conexion activa."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _ensure_wide_version_table(connection) -> None:
    """Alembic crea alembic_version.version_num como VARCHAR(32) por defecto.
    Varias revisiones de este repo superan ese limite (ej.
    "0055_device_asset_lock_and_field_tokens", 39 caracteres) -- en Postgres
    esto revienta con StringDataRightTruncation al intentar escribir la
    version. SQLite no aplica limites de longitud de VARCHAR, por eso nunca
    se noto antes (docs/117): este proyecto solo se habia migrado contra
    SQLite hasta la primera prueba real contra Postgres."""
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS alembic_version ("
        "version_num VARCHAR(255) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    ))
    connection.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))
    connection.commit()


def run_migrations_online() -> None:
    """Ejecuta migraciones con conexion activa."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            _ensure_wide_version_table(connection)

        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
