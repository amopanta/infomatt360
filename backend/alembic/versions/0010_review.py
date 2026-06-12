from alembic import op
import sqlalchemy as sa

revision = "0010_review"
down_revision = "0009_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_actions")
