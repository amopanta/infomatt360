"""Bandeja externa de correo via IMAP (docs/96 item #11): tabla external_mail_messages
y columna last_imap_uid en mail_profiles.

Revision ID: 0069_external_mail_messages
Revises: 0068_gis_geometry_column
"""

from alembic import op
import sqlalchemy as sa

revision = "0069_external_mail_messages"
down_revision = "0068_gis_geometry_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    mail_profile_columns = {col["name"] for col in inspector.get_columns("mail_profiles")}
    if "last_imap_uid" not in mail_profile_columns:
        op.add_column("mail_profiles", sa.Column("last_imap_uid", sa.Integer(), nullable=True))

    if "external_mail_messages" not in inspector.get_table_names():
        op.create_table(
            "external_mail_messages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("mail_profile_id", sa.String(length=36), nullable=False),
            sa.Column("uid", sa.Integer(), nullable=False),
            sa.Column("from_address", sa.String(length=320), nullable=False),
            sa.Column("subject", sa.String(length=250), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.UniqueConstraint("mail_profile_id", "uid", name="uq_external_mail_messages_profile_uid"),
        )
        op.create_index("ix_external_mail_messages_project_id", "external_mail_messages", ["project_id"])
        op.create_index("ix_external_mail_messages_mail_profile_id", "external_mail_messages", ["mail_profile_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "external_mail_messages" in inspector.get_table_names():
        op.drop_index("ix_external_mail_messages_mail_profile_id", table_name="external_mail_messages")
        op.drop_index("ix_external_mail_messages_project_id", table_name="external_mail_messages")
        op.drop_table("external_mail_messages")
    mail_profile_columns = {col["name"] for col in inspector.get_columns("mail_profiles")}
    if "last_imap_uid" in mail_profile_columns:
        op.drop_column("mail_profiles", "last_imap_uid")
