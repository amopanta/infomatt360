from alembic import op
import sqlalchemy as sa

revision = "0053_ai_audit_config"
down_revision = "0052_integration_donor_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_audit_configs" in inspector.get_table_names():
        return
    op.create_table(
        "ai_audit_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("text_field_name", sa.String(length=180), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_audit_configs_template_id", "ai_audit_configs", ["template_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ai_audit_configs_template_id", table_name="ai_audit_configs")
    op.drop_table("ai_audit_configs")
