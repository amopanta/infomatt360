"""Estado de instalacion de primer arranque.

Fila unica (patron singleton de tabla). Su ausencia se interpreta como
"instalado" cuando `settings.installer_enforced` esta desactivado, para no
afectar despliegues existentes.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class InstallationState(Base):
    __tablename__ = "installation_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    is_installed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
