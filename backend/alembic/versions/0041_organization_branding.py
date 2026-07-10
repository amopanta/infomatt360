from alembic import op
import sqlalchemy as sa

revision = "0041_organization_branding"
down_revision = "0040_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "organization_brandings" in inspector.get_table_names():
        return
    op.create_table(
        "organization_brandings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=True),
        sa.Column("accent_color", sa.String(length=20), nullable=True),
        sa.Column("background_color", sa.String(length=20), nullable=True),
        sa.Column("slogan", sa.String(length=220), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_organization_brandings_organization_id"),
    )
    op.create_index("ix_organization_brandings_organization_id", "organization_brandings", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_organization_brandings_organization_id", table_name="organization_brandings")
    op.drop_table("organization_brandings")
