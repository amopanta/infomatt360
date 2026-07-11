from alembic import op
import sqlalchemy as sa

revision = "0051_whatsapp_notifications"
down_revision = "0050_erp_headless"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "whatsapp_notifications" in inspector.get_table_names():
        return
    op.create_table(
        "whatsapp_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_phone", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reference_record_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_notifications_project_id", "whatsapp_notifications", ["project_id"])
    op.create_index("ix_whatsapp_notifications_recipient_user_id", "whatsapp_notifications", ["recipient_user_id"])
    op.create_index("ix_whatsapp_notifications_reference_record_id", "whatsapp_notifications", ["reference_record_id"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_notifications_reference_record_id", table_name="whatsapp_notifications")
    op.drop_index("ix_whatsapp_notifications_recipient_user_id", table_name="whatsapp_notifications")
    op.drop_index("ix_whatsapp_notifications_project_id", table_name="whatsapp_notifications")
    op.drop_table("whatsapp_notifications")
