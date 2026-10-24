"""Pasos del asistente que tocan infraestructura: base de datos y correo
(docs/151).

Base de datos: la incluida (PostgreSQL del propio despliegue) no pide nada.
Para una externa se prueba la conexión, se crean o actualizan las tablas con
Alembic y se guarda la dirección en la configuración del asistente; los
procesos se reinician solos para usarla (runtime_config.watch_for_changes).
Solo PostgreSQL: es el motor de la base principal. MySQL y SQL Server siguen
disponibles como destino de copias (Bases de datos externas, docs/146).
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import HTTPException, status
from sqlalchemy import create_engine, inspect, text

from app.core import runtime_config
from app.core.config import settings


def database_url(host: str, port: int, name: str, username: str, password: str, sslmode: str | None = None) -> str:
    url = f"postgresql+psycopg2://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{quote_plus(name)}"
    return f"{url}?sslmode={sslmode}" if sslmode else url


def _safe_error(exc: Exception) -> str:
    """El mensaje del controlador puede traer la dirección completa; se deja
    solo la primera línea y nunca la contraseña."""
    message = str(getattr(exc, "orig", exc)).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return message[:300]


def test_database(url: str) -> dict:
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 8} if url.startswith("postgresql") else {})
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version()")).scalar_one()
            tables = set(inspect(connection).get_table_names())
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar() if "alembic_version" in tables else None
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"No se pudo conectar: {_safe_error(exc)}") from exc
    finally:
        engine.dispose()
    foreign = sorted(tables - {"alembic_version"}) if revision is None else []
    return {
        "server_version": str(version).split(",")[0],
        "empty": not tables,
        "current_revision": revision,
        # Tablas ajenas sin versión de InfoMatt360: no se instala encima.
        "usable": revision is not None or not foreign,
        "foreign_tables": foreign[:10],
    }


def apply_database(url: str) -> dict:
    """Prueba, migra y guarda. El reinicio lo hace el vigilante del archivo."""
    result = test_database(url)
    if not result["usable"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="La base tiene tablas que no son de InfoMatt360. Usa una base vacía o una de InfoMatt360.")
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.attributes["database_url"] = url
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"No se pudieron crear las tablas: {_safe_error(exc)}") from exc
    runtime_config.save(settings.runtime_config_dir, {"database_url": url})
    return {**test_database(url), "restarting": settings.runtime_config_watch}


def use_bundled_database() -> dict:
    """Vuelve a la base incluida: borra la dirección externa guardada."""
    data = runtime_config.load(settings.runtime_config_dir)
    if "database_url" in data:
        data.pop("database_url")
        path = runtime_config.config_path(settings.runtime_config_dir)
        path.unlink(missing_ok=True)
        if data:
            runtime_config.save(settings.runtime_config_dir, data)
        return {"restarting": settings.runtime_config_watch}
    return {"restarting": False}


def send_test_mail(host: str, port: int, username: str, password: str, use_tls: bool, sender: str, recipient: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Prueba de correo de InfoMatt360"
    message["From"] = sender
    message["To"] = recipient
    message.set_content("Este es un correo de prueba enviado desde el asistente de instalación de InfoMatt360. Si lo recibes, el correo quedó bien configurado.")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as server:
                if username:
                    server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                if username:
                    server.login(username, password)
                server.send_message(message)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"No se pudo enviar: {_safe_error(exc)}") from exc


def save_mail(host: str, port: int, username: str, password: str, use_tls: bool, sender: str) -> None:
    runtime_config.save(settings.runtime_config_dir, {
        "smtp_host": host, "smtp_port": port, "smtp_username": username, "smtp_password": password,
        "smtp_use_tls": use_tls, "smtp_from_email": sender,
    })
    # El correo no necesita reinicio: se aplica también en este proceso.
    for key, value in {"smtp_host": host, "smtp_port": port, "smtp_username": username, "smtp_password": password,
                       "smtp_use_tls": use_tls, "smtp_from_email": sender}.items():
        setattr(settings, key, value)
