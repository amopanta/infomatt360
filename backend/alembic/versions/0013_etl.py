from alembic import op
import sqlalchemy as sa

revision = "0013_etl"
down_revision = "0012_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etl_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("rule_type", sa.String(length=60), nullable=False),
        sa.Column("source_field", sa.String(length=180), nullable=True),
        sa.Column("target_field", sa.String(length=180), nullable=True),
        sa.Column("operator", sa.String(length=60), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "etl_pipelines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("steps_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("etl_pipelines")
    op.drop_table("etl_rules")
