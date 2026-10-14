"""Perfil MFA separado del modelo User (docs/96 Categoría D).

Extrae los campos mfa_* y device_lock_* del modelo User monolítico a su
propia tabla con relación 1:1.  El servicio MFA lee de aquí primero y cae
a los campos legacy de User para compatibilidad con bases existentes.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base
from app.models.identity import new_uuid


class UserMfaProfile(Base):
    __tablename__ = "user_mfa_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_mfa_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # --- MFA TOTP ---
    secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_hashes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Device lock ---
    locked_device_fingerprint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    device_lock_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
