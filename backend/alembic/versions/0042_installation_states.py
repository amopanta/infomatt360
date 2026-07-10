from alembic import op
import sqlalchemy as sa

revision = "0042_installation_states"
down_revision = "0041_organization_branding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "installation_states" in inspector.get_table_names():
        return
    op.create_table(
        "installation_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("is_installed", sa.Boolean(), nullable=False),
        sa.Column("installed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("installation_states")
