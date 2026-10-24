"""Configuración escrita por el asistente de instalación (docs/151).

El asistente guarda aquí lo que antes había que poner a mano en
`.env.production`: la base de datos externa y el correo (SMTP). El archivo
vive en un volumen propio (`/app/config` en Docker), con permisos 600, y al
arrancar tiene prioridad sobre las variables de entorno.

Cambiar la base de datos exige reiniciar el proceso, porque el motor de
SQLAlchemy se crea al importar `app.db.session`. Por eso, cuando el archivo
cambia, `watch_for_changes` termina el proceso y Docker lo vuelve a levantar
(`restart: unless-stopped`) ya con la configuración nueva. Así se reinician
juntos los dos servidores y los procesos de fondo.

Este módulo no importa `app.core.config` para evitar un ciclo.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("infomatt360.runtime_config")

FILE_NAME = "runtime.json"
# Solo estas claves se pueden escribir desde el asistente. Cualquier otra se
# ignora al leer, para que el archivo no sirva de puerta a otros ajustes.
ALLOWED_KEYS = {
    "database_url",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_password",
    "smtp_from_email",
    "smtp_use_tls",
}


def config_path(directory: str) -> Path:
    return Path(directory) / FILE_NAME


def load(directory: str) -> dict[str, Any]:
    path = config_path(directory)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.error("No se pudo leer %s; se ignora", path)
        return {}
    return {key: value for key, value in data.items() if key in ALLOWED_KEYS} if isinstance(data, dict) else {}


def save(directory: str, updates: dict[str, Any]) -> None:
    """Mezcla `updates` con lo guardado y escribe de forma atómica (600)."""
    unknown = set(updates) - ALLOWED_KEYS
    if unknown:
        raise ValueError(f"Claves no permitidas: {', '.join(sorted(unknown))}")
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    data = {**load(directory), **updates}
    handle, temporary = tempfile.mkstemp(dir=folder, prefix=".runtime-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.chmod(temporary, 0o600)
        os.replace(temporary, config_path(directory))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def apply(settings: Any) -> None:
    """Aplica lo guardado sobre la configuración ya cargada del entorno."""
    for key, value in load(settings.runtime_config_dir).items():
        setattr(settings, key, value)


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def watch_for_changes(directory: str, interval_seconds: float = 3.0, on_change=None) -> threading.Thread:
    """Vigila el archivo y, si cambia, termina el proceso para que Docker lo
    reinicie con la configuración nueva."""
    path = config_path(directory)
    initial = _mtime(path)

    def stop() -> None:
        logger.warning("La configuración del asistente cambió; reiniciando el proceso")
        os._exit(3)

    action = on_change or stop

    def loop() -> None:
        while True:
            time.sleep(interval_seconds)
            if _mtime(path) != initial:
                action()
                return

    thread = threading.Thread(target=loop, name="runtime-config-watch", daemon=True)
    thread.start()
    return thread
