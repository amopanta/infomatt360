from alembic import op
import sqlalchemy as sa

revision = "0058_builder_public_links"
down_revision = "0057_runtime_record_lock_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "builder_public_links" in inspector.get_table_names():
        return

    op.create_table(
        "builder_public_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=180), nullable=True),
        sa.Column("max_submissions", sa.Integer(), nullable=True),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_builder_public_links_project_id", "builder_public_links", ["project_id"])
    op.create_index("ix_builder_public_links_template_id", "builder_public_links", ["template_id"])
    op.create_index("ix_builder_public_links_token_hash", "builder_public_links", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_builder_public_links_token_hash", table_name="builder_public_links")
    op.drop_index("ix_builder_public_links_template_id", table_name="builder_public_links")
    op.drop_index("ix_builder_public_links_project_id", table_name="builder_public_links")
    op.drop_table("builder_public_links")
