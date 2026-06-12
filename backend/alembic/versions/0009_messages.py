from alembic import op
import sqlalchemy as sa

revision = "0009_messages"
down_revision = "0008_store_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("sender_email", sa.String(length=180), nullable=False),
        sa.Column("server_host", sa.String(length=180), nullable=True),
        sa.Column("server_port", sa.String(length=20), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("is_default", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "internal_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=250), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("internal_messages")
    op.drop_table("mail_profiles")
