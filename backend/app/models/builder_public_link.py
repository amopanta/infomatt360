"""Enlaces publicos de captura sin cuenta (formularios abiertos, estilo LimeSurvey).

El token nunca se guarda en texto plano (solo su hash SHA-256), igual que
`ManagerQrToken` y `EmergencyAccessKey`. A diferencia de ambos, este token
no es necesariamente de un solo uso: `max_submissions=None` representa un
enlace "abierto" (respuestas ilimitadas mientras no expire ni se revoque);
`max_submissions=N` representa un enlace "controlado" que se cierra solo
despues de N envios exitosos.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class BuilderPublicLink(Base):
    __tablename__ = "builder_public_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(180), nullable=True)
    max_submissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submission_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
