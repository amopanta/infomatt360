"""Enlaces publicos de captura sin cuenta (formularios abiertos).

Ver `backend/app/models/builder_public_link.py` para el diseno del token.
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import or_, update as sa_update
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.builder import BuilderTemplate
from app.models.builder_public_link import BuilderPublicLink
from app.schemas.builder_public_link import BuilderPublicLinkCreate, BuilderPublicLinkIssued, BuilderPublicLinkRead


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _to_read(row: BuilderPublicLink) -> BuilderPublicLinkRead:
    return BuilderPublicLinkRead(
        id=row.id,
        project_id=row.project_id,
        template_id=row.template_id,
        label=row.label,
        max_submissions=row.max_submissions,
        submission_count=row.submission_count,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


class BuilderPublicLinkService:
    def create_link(self, db: Session, payload: BuilderPublicLinkCreate, created_by: str | None) -> BuilderPublicLinkIssued:
        template = db.query(BuilderTemplate).filter(BuilderTemplate.id == payload.template_id).first()
        if template is None:
            raise ValueError("Plantilla no encontrada")
        if template.status != "published":
            raise ValueError("Solo se puede generar un enlace publico para una plantilla publicada")

        raw_token = secrets.token_urlsafe(32)
        row = BuilderPublicLink(
            project_id=template.project_id,
            template_id=template.id,
            token_hash=_hash_token(raw_token),
            label=payload.label,
            max_submissions=payload.max_submissions,
            expires_at=utc_now() + timedelta(hours=payload.expires_in_hours) if payload.expires_in_hours else None,
            created_by=created_by,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return BuilderPublicLinkIssued(**_to_read(row).model_dump(), token=raw_token)

    def get_link(self, db: Session, link_id: str) -> BuilderPublicLink | None:
        return db.query(BuilderPublicLink).filter(BuilderPublicLink.id == link_id).first()

    def list_links(self, db: Session, template_id: str) -> list[BuilderPublicLinkRead]:
        rows = db.query(BuilderPublicLink).filter(BuilderPublicLink.template_id == template_id).order_by(BuilderPublicLink.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def revoke_link(self, db: Session, link_id: str) -> BuilderPublicLinkRead:
        row = self.get_link(db, link_id)
        if row is None:
            raise ValueError("Enlace publico no encontrado")
        if row.revoked_at is None:
            row.revoked_at = utc_now()
            db.commit()
            db.refresh(row)
        return _to_read(row)

    def validate_token(self, db: Session, raw_token: str) -> BuilderPublicLink:
        row = db.query(BuilderPublicLink).filter(BuilderPublicLink.token_hash == _hash_token(raw_token)).first()
        now = utc_now()
        if row is None or row.revoked_at is not None or (row.expires_at is not None and row.expires_at <= now):
            raise ValueError("Enlace publico invalido, vencido o revocado")
        if row.max_submissions is not None and row.submission_count >= row.max_submissions:
            raise ValueError("Este enlace publico ya alcanzo el maximo de respuestas permitidas")
        return row

    def reserve_submission_slot(self, db: Session, link: BuilderPublicLink) -> None:
        """Reserva atomicamente un cupo de envio antes de guardar el registro.

        `validate_token` por si solo tiene una ventana TOCTOU: dos envios
        simultaneos sobre un enlace de un solo uso podrian pasar la
        validacion antes de que cualquiera incremente el contador. Este
        UPDATE condicional (`WHERE ... AND cupo_disponible`) hace que solo
        una de las dos peticiones concurrentes reserve el cupo; la otra
        recibe `rowcount == 0` y se rechaza.
        """
        result = db.execute(
            sa_update(BuilderPublicLink)
            .where(
                BuilderPublicLink.id == link.id,
                or_(BuilderPublicLink.max_submissions.is_(None), BuilderPublicLink.submission_count < BuilderPublicLink.max_submissions),
            )
            .values(submission_count=BuilderPublicLink.submission_count + 1)
        )
        db.commit()
        if result.rowcount == 0:
            raise ValueError("Este enlace publico ya alcanzo el maximo de respuestas permitidas")


builder_public_link_service = BuilderPublicLinkService()
