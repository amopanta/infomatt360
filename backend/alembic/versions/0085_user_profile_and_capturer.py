"""Perfil del usuario (cargo y municipio) y copia de quién capturó cada registro (docs/145)."""

from alembic import op
import sqlalchemy as sa

revision = "0085_user_profile_capturer"
down_revision = "0084_planner"
branch_labels = None
depends_on = None

USER_COLUMNS = (("position", 120), ("department", 120), ("municipality", 120))
RECORD_COLUMNS = (("captured_by_name", 180), ("captured_by_document", 50), ("captured_by_position", 120),
                  ("captured_by_department", 120), ("captured_by_municipality", 120))


def upgrade() -> None:
    for name, size in USER_COLUMNS:
        op.add_column("users", sa.Column(name, sa.String(size), nullable=True))
    for name, size in RECORD_COLUMNS:
        op.add_column("runtime_records", sa.Column(name, sa.String(size), nullable=True))
    # Registros anteriores: nombre y documento actuales de quien los envió. El
    # cargo y el municipio no existían, así que quedan vacíos.
    op.execute(
        "UPDATE runtime_records SET "
        "captured_by_name = (SELECT users.full_name FROM users WHERE users.id = runtime_records.submitted_by), "
        "captured_by_document = (SELECT users.document_id FROM users WHERE users.id = runtime_records.submitted_by) "
        "WHERE submitted_by IS NOT NULL"
    )


def downgrade() -> None:
    for name, _ in RECORD_COLUMNS:
        op.drop_column("runtime_records", name)
    for name, _ in USER_COLUMNS:
        op.drop_column("users", name)
