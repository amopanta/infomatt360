"""Auditoria semantica con IA sobre observaciones de campo en texto libre.

La especificacion original describe una "aduana avanzada basada en
procesamiento de lenguaje natural" que analiza las cajas de texto de
"observaciones de campo" buscando contradicciones humanas o indicios de
fraude, y puede provocar el rechazo automatico del formulario.

Alcance de esta implementacion, acordado con el usuario:

- El modo de reaccion es configurable por plantilla (`AiAuditConfig.mode`):
  "human" (solo alerta, nunca rechaza solo), "automatic" (cualquier riesgo
  detectado rechaza el registro sin intervencion humana, tal como describe
  el documento original) o "mixed" (solo el riesgo "high" rechaza solo;
  "possible" queda como alerta para un revisor).
- Soporta multiples proveedores de LLM detras de un adaptador comun:
  Anthropic (Claude), cualquier proveedor compatible con el esquema de
  "chat completions" de OpenAI (esto cubre OpenAI, DeepSeek, Zhipu/GLM y
  otros con solo cambiar la URL base) y Gemini. Inactivo por defecto (sin
  `AI_AUDIT_PROVIDER` configurado) -- no bloquea ni afecta el guardado
  normal de registros.
- Se ejecuta *despues* de que el registro ya quedo guardado (ver
  `runtime_record_service.save_record`), nunca antes: la captura de datos
  en campo no debe perderse ni demorarse por una llamada a un servicio de
  IA externo lento o caido. Un fallo de la llamada se registra como
  `status="error"` y no cambia el estado del registro.
"""

import json
import logging
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import AiAuditConfig, AiCheck
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.ai import AiAuditConfigCreate, AiAuditConfigRead, AiCheckRead

logger = logging.getLogger(__name__)

AUDIT_TIMEOUT_SECONDS = 20
RISK_LEVELS = {"none", "possible", "high"}

PROMPT_TEMPLATE = """Eres un auditor de calidad de datos humanitarios. Analiza el siguiente texto de observaciones de campo escrito por un gestor territorial. Busca contradicciones logicas o indicios de fraude (por ejemplo: afirmar que una entrega se recibio completa pero luego mencionar que falto algo, o afirmar haber hecho una visita presencial pero mencionar que en realidad fue por telefono).

Texto a analizar:
\"\"\"
{text}
\"\"\"

Responde UNICAMENTE con un JSON valido, sin texto adicional antes ni despues, con esta forma exacta:
{{"risk_level": "none" | "possible" | "high", "reasoning": "explicacion breve en espanol", "flagged_phrases": ["frase textual detectada", ...]}}
"""


def _config_to_read(row: AiAuditConfig) -> AiAuditConfigRead:
    return AiAuditConfigRead(id=row.id, template_id=row.template_id, text_field_name=row.text_field_name, mode=row.mode, created_at=row.created_at)


def _check_to_read(row: AiCheck) -> AiCheckRead:
    return AiCheckRead(id=row.id, project_id=row.project_id, record_id=row.record_id, file_id=row.file_id, check_type=row.check_type, status=row.status, result_json=row.result_json, created_by=row.created_by, created_at=row.created_at)


def _parse_text_value(raw_json: str) -> str:
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError:
        return raw_json
    return str(value) if value is not None else ""


def _extract_json_object(raw_text: str) -> dict[str, object]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("La respuesta del modelo no contiene un JSON valido")


class AiAuditService:
    def is_configured(self) -> bool:
        return bool(settings.ai_audit_provider and settings.ai_audit_api_key)

    # --- Configuracion por plantilla ---

    def create_config(self, db: Session, payload: AiAuditConfigCreate) -> AiAuditConfigRead:
        row = AiAuditConfig(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _config_to_read(row)

    def get_config(self, db: Session, template_id: str) -> AiAuditConfigRead | None:
        row = db.query(AiAuditConfig).filter(AiAuditConfig.template_id == template_id).first()
        return _config_to_read(row) if row else None

    # --- Auditoria ---

    def audit_record(self, db: Session, record: RuntimeRecord) -> AiCheckRead | None:
        """Analiza el campo de texto configurado y aplica el modo de reaccion.

        No-op silencioso si la plantilla no tiene `AiAuditConfig`, o si el
        campo configurado esta vacio en este registro. Nunca lanza: un
        fallo del proveedor de IA se registra como `status="error"` y deja
        el registro sin cambios.
        """
        config = db.query(AiAuditConfig).filter(AiAuditConfig.template_id == record.template_id).first()
        if config is None:
            return None

        value_row = db.query(RuntimeRecordValue).filter(
            RuntimeRecordValue.record_id == record.id,
            RuntimeRecordValue.field_name == config.text_field_name,
        ).first()
        text = _parse_text_value(value_row.field_value_json).strip() if value_row else ""
        if not text:
            return None

        if not self.is_configured():
            return self._store_check(db, record, status_value="skipped", result={"reason": "Proveedor de IA no configurado (AI_AUDIT_PROVIDER vacio)"})

        try:
            raw_response = self._call_llm(PROMPT_TEMPLATE.format(text=text))
            parsed = _extract_json_object(raw_response)
            risk_level = str(parsed.get("risk_level", "")).lower()
            if risk_level not in RISK_LEVELS:
                raise ValueError(f"risk_level inesperado: {parsed.get('risk_level')!r}")
        except Exception as exc:
            logger.warning("Fallo la auditoria semantica del registro %s: %s", record.id, exc)
            return self._store_check(db, record, status_value="error", result={"error": str(exc)[:500]})

        check = self._store_check(db, record, status_value=risk_level, result={
            "reasoning": parsed.get("reasoning"),
            "flagged_phrases": parsed.get("flagged_phrases", []),
            "text_analyzed": text,
            "provider": settings.ai_audit_provider,
        })
        self._apply_mode(db, record, config.mode, risk_level)
        return check

    def _apply_mode(self, db: Session, record: RuntimeRecord, mode: str, risk_level: str) -> None:
        should_reject = (
            (mode == "automatic" and risk_level in ("possible", "high"))
            or (mode == "mixed" and risk_level == "high")
        )
        if should_reject and record.status not in ("rejected", "approved", "archived"):
            record.status = "rejected"
            db.add(record)
            db.commit()

    def _store_check(self, db: Session, record: RuntimeRecord, *, status_value: str, result: dict[str, object]) -> AiCheckRead:
        row = AiCheck(
            project_id=record.project_id,
            record_id=record.id,
            check_type="semantic_audit",
            status=status_value,
            result_json=json.dumps(result, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _check_to_read(row)

    # --- Adaptadores de proveedor ---

    def _call_llm(self, prompt: str) -> str:
        if settings.ai_audit_provider == "anthropic":
            return self._call_anthropic(prompt)
        if settings.ai_audit_provider == "gemini":
            return self._call_gemini(prompt)
        if settings.ai_audit_provider == "openai_compatible":
            return self._call_openai_compatible(prompt)
        raise ValueError(f"Proveedor de IA no soportado: {settings.ai_audit_provider!r}")

    def _call_anthropic(self, prompt: str) -> str:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ai_audit_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.ai_audit_model or "claude-sonnet-5",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=AUDIT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    def _call_openai_compatible(self, prompt: str) -> str:
        """Cubre OpenAI, DeepSeek, Zhipu/GLM y cualquier otro proveedor que
        implemente el esquema de "chat completions" de OpenAI -- solo
        cambia `AI_AUDIT_BASE_URL` y `AI_AUDIT_MODEL`."""
        base_url = (settings.ai_audit_base_url or "https://api.openai.com/v1").rstrip("/")
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.ai_audit_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.ai_audit_model or "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=AUDIT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _call_gemini(self, prompt: str) -> str:
        model = settings.ai_audit_model or "gemini-1.5-flash"
        base_url = (settings.ai_audit_base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        response = httpx.post(
            f"{base_url}/models/{model}:generateContent?key={settings.ai_audit_api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=AUDIT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


ai_audit_service = AiAuditService()
