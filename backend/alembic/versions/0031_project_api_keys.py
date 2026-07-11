from alembic import op
import sqlalchemy as sa

revision = "0031_project_api_keys"
down_revision = "0030_approval_flows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("permissions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id"),
    )
    op.create_index("ix_project_api_keys_project_id", "project_api_keys", ["project_id"])
    op.create_index("ix_project_api_keys_key_id", "project_api_keys", ["key_id"])
    op.create_index("ix_project_api_keys_status", "project_api_keys", ["status"])
    op.create_index("ix_project_api_keys_created_by", "project_api_keys", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_project_api_keys_created_by", table_name="project_api_keys")
    op.drop_index("ix_project_api_keys_status", table_name="project_api_keys")
    op.drop_index("ix_project_api_keys_key_id", table_name="project_api_keys")
    op.drop_index("ix_project_api_keys_project_id", table_name="project_api_keys")
    op.drop_table("project_api_keys")
