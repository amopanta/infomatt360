from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class AiCheck(Base):
    __tablename__ = "ai_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    check_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AiAuditConfig(Base):
    """Vincula una plantilla del Builder a la auditoria semantica con IA.

    Una plantilla sin fila aqui no dispara ningun analisis al guardarse un
    registro -- la mayoria de formularios no tienen un campo de texto libre
    relevante para auditar. `mode` decide que pasa cuando el modelo detecta
    una posible contradiccion o indicio de fraude:

    - "human": solo se guarda la alerta (AiCheck); un revisor decide.
    - "automatic": cualquier riesgo detectado ("possible" o "high") rechaza
      el registro automaticamente, sin intervencion humana.
    - "mixed": solo el riesgo "high" rechaza automaticamente; "possible"
      queda como alerta para que un humano decida.
    """

    __tablename__ = "ai_audit_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    text_field_name: Mapped[str] = mapped_column(String(180), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="human", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class OcrResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    text_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ExecutiveAnalysis(Base):
    __tablename__ = "executive_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
