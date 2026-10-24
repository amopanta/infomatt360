"""Código de instalación y de recuperación (docs/151).

Como en Grafana o Jupyter: el asistente web solo se usa con un código que ve
quien tiene acceso al servidor (en el registro del contenedor o con
`python -m app.cli.install_code`). Evita que otra persona abra /install
antes que el responsable y se quede con el sistema.

- «setup»: mientras el sistema no está instalado. No vence.
- «recovery»: con el sistema instalado, para crear o recuperar un
  administrador desde la web. Vence a los 30 minutos y sirve una vez.

Solo se guarda el hash del código, en la carpeta de configuración del
asistente (permisos 600).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("infomatt360.install_code")

FILE_NAME = "install_code.json"
# Sin letras ni números que se confundan al leerlos de una pantalla (0/O, 1/I/L).
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
RECOVERY_MINUTES = 30


def _path() -> Path:
    return Path(settings.runtime_config_dir) / FILE_NAME


def _hash(code: str) -> str:
    return hashlib.sha256(normalize(code).encode("utf-8")).hexdigest()


def normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _read() -> dict | None:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write(data: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def generate(kind: str) -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    code = f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=RECOVERY_MINUTES)).isoformat() if kind == "recovery" else None
    _write({"kind": kind, "hash": _hash(code), "expires_at": expires})
    return code


def ensure_setup_code() -> str | None:
    """Al arrancar sin instalar: crea el código si no existe y lo deja en el
    registro. Devuelve el código solo cuando lo acaba de crear."""
    current = _read()
    if current and current.get("kind") == "setup":
        return None
    code = generate("setup")
    logger.warning("Código de instalación de InfoMatt360: %s (ábrelo en /install)", code)
    return code


def verify(code: str, kind: str) -> bool:
    data = _read()
    if not data or data.get("kind") != kind or not code:
        return False
    if data.get("expires_at") and datetime.fromisoformat(data["expires_at"]) < datetime.now(timezone.utc):
        return False
    return hmac.compare_digest(str(data.get("hash", "")), _hash(code))


def consume() -> None:
    """Invalida el código después de usarlo (recuperación y fin de instalación)."""
    _path().unlink(missing_ok=True)
