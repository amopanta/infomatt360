import re
import unicodedata
from datetime import datetime
from pathlib import Path


def _slug_component(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.strip())
    ascii_only = "".join(character for character in normalized if not unicodedata.combining(character))
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-")
    return slug or "Sin-Nombre"


def build_evidence_filename(
    *,
    participant_name: str | None,
    asset_type: str,
    created_at: datetime,
    original_name: str,
    used: set[str],
) -> str:
    """Renombrado automatico Participante_TipoEvidencia_Fecha (docs/96 #7,
    decision acordada con el usuario). Colisiones (mismo participante+tipo+
    fecha, o coincidencia de nombre) se resuelven con un sufijo _2, _3...
    via el set `used` -- mismo patron que _slugify en
    multi_format_import_service.py."""
    participant_part = _slug_component(participant_name) if participant_name else "Sin-Participante"
    date_part = created_at.date().isoformat()
    extension = Path(original_name).suffix.lower() or ""
    base = f"{participant_part}_{asset_type}_{date_part}"
    candidate = f"{base}{extension}"
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}{extension}"
        index += 1
    used.add(candidate)
    return candidate
