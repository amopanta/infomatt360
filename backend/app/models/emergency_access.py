"""Credenciales de emergencia con expiracion (time-boxed).

El codigo nunca se guarda en texto plano, solo su hash, igual que
ManagerQrToken y PasswordResetToken. Al canjearse concede una sesion
normal para el usuario indicado, pero con una expiracion recortada al
minimo entre la configuracion habitual del JWT y el vencimiento propio
de la llave de emergencia.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class EmergencyAccessKey(Base):
    __tablename__ = "emergency_access_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    issued_by: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
