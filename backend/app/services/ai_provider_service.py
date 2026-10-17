"""Conexiones de IA por proyecto sobre el almacén cifrado de integraciones."""

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.security import decrypt_text, encrypt_text
from app.models.integrations import IntegrationSource
from app.services.integration_service import _assert_safe_outbound_url


PROVIDERS = {
    "gemini": ("gemini", "https://generativelanguage.googleapis.com/v1beta"),
    "anthropic": ("anthropic", "https://api.anthropic.com/v1"),
    "openai": ("openai_compatible", "https://api.openai.com/v1"),
    "openrouter": ("openai_compatible", "https://openrouter.ai/api/v1"),
    "deepseek": ("openai_compatible", "https://api.deepseek.com"),
    "groq": ("openai_compatible", "https://api.groq.com/openai/v1"),
    "custom": ("openai_compatible", ""),
}


@dataclass(frozen=True)
class AiConnection:
    provider: str
    api_key: str
    model: str
    base_url: str


def validate_provider(kind: str, model: str, base_url: str) -> tuple[str, str]:
    if kind not in PROVIDERS:
        raise ValueError("Proveedor de IA no admitido")
    model = model.strip()
    if not 2 <= len(model) <= 120:
        raise ValueError("Indica el identificador del modelo")
    adapter, preset_url = PROVIDERS[kind]
    url = preset_url if kind != "custom" else base_url.strip().rstrip("/")
    if kind == "custom":
        if not url.startswith("https://") or url.endswith("/chat/completions"):
            raise ValueError("Indica la URL base pública HTTPS, sin /chat/completions")
        _assert_safe_outbound_url(url)
    return adapter, url


def provider_to_read(row: IntegrationSource) -> dict:
    config = json.loads(row.config_json or "{}")
    return {
        "id": row.id, "project_id": row.project_id, "name": row.name,
        "provider": config.get("provider", "custom"), "model": config.get("model", ""),
        "base_url": row.base_url if config.get("provider") == "custom" else "",
        "status": row.status, "has_key": bool(row.credentials_encrypted),
    }


def list_providers(db: Session, project_id: str) -> list[IntegrationSource]:
    return db.query(IntegrationSource).filter(
        IntegrationSource.project_id == project_id,
        IntegrationSource.source_type == "ai_provider",
        IntegrationSource.status != "deleted",
    ).order_by(IntegrationSource.created_at).all()


def get_provider(db: Session, project_id: str, provider_id: str) -> IntegrationSource | None:
    return db.query(IntegrationSource).filter(
        IntegrationSource.id == provider_id, IntegrationSource.project_id == project_id,
        IntegrationSource.source_type == "ai_provider", IntegrationSource.status != "deleted",
    ).first()


def save_provider(db: Session, *, project_id: str, name: str, kind: str, model: str,
                  base_url: str, api_key: str, status: str, row: IntegrationSource | None = None) -> IntegrationSource:
    adapter, url = validate_provider(kind, model, base_url)
    if status not in ("active", "disabled"):
        raise ValueError("Estado no válido")
    if not name.strip() or len(name.strip()) > 180:
        raise ValueError("Indica un nombre de conexión")
    if not row and not api_key.strip():
        raise ValueError("La clave de API es obligatoria")
    row = row or IntegrationSource(project_id=project_id, source_type="ai_provider")
    row.name = name.strip()
    row.base_url = url
    row.config_json = json.dumps({"provider": kind, "adapter": adapter, "model": model.strip()})
    row.status = status
    if api_key.strip():
        row.credentials_encrypted = encrypt_text(api_key.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def connection_for(row: IntegrationSource) -> AiConnection:
    config = json.loads(row.config_json or "{}")
    adapter, url = validate_provider(config["provider"], config["model"], row.base_url or "")
    if not row.credentials_encrypted:
        raise ValueError("La conexión no tiene clave de API")
    return AiConnection(adapter, decrypt_text(row.credentials_encrypted), config["model"], url)
