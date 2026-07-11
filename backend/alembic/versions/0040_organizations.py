from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0040_organizations"
down_revision = "0039_template_theme_json"
branch_labels = None
depends_on = None

DEFAULT_ORG_SLUG = "default"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "organizations" not in table_names:
        op.create_table(
            "organizations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        )
        op.create_index("ix_organizations_slug", "organizations", ["slug"])

    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "organization_id" not in project_columns:
        op.add_column("projects", sa.Column("organization_id", sa.String(length=36), nullable=True))
        op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    organizations = sa.table(
        "organizations",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    projects = sa.table("projects", sa.column("id", sa.String), sa.column("organization_id", sa.String))

    existing_default = bind.execute(
        sa.text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": DEFAULT_ORG_SLUG}
    ).first()
    default_org_id = existing_default[0] if existing_default else str(uuid4())
    if existing_default is None:
        bind.execute(
            organizations.insert().values(
                id=default_org_id,
                name="Organizacion por defecto",
                slug=DEFAULT_ORG_SLUG,
                status="active",
                created_at=_utc_now_naive(),
            )
        )

    bind.execute(
        projects.update().where(projects.c.organization_id.is_(None)).values(organization_id=default_org_id)
    )


def downgrade() -> None:
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_column("projects", "organization_id")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
