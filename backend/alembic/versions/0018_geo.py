from alembic import op
import sqlalchemy as sa

revision = "0018_geo"
down_revision = "0017_ai_ocr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geo_layers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("style_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "geo_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("layer_id", sa.String(length=36), nullable=True),
        sa.Column("item_type", sa.String(length=60), nullable=False),
        sa.Column("lat", sa.String(length=60), nullable=True),
        sa.Column("lng", sa.String(length=60), nullable=True),
        sa.Column("data_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("geo_items")
    op.drop_table("geo_layers")
