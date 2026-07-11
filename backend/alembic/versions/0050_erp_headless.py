from alembic import op
import sqlalchemy as sa

revision = "0050_erp_headless"
down_revision = "0049_acta_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "erp_template_configs" not in existing_tables:
        op.create_table(
            "erp_template_configs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("template_id", sa.String(length=36), nullable=False),
            sa.Column("sku_field_name", sa.String(length=180), nullable=False),
            sa.Column("quantity_field_name", sa.String(length=180), nullable=False),
            sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_erp_template_configs_template_id", "erp_template_configs", ["template_id"], unique=True)

    if "erp_inventory_items" not in existing_tables:
        op.create_table(
            "erp_inventory_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("sku", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("unit", sa.String(length=30), nullable=False),
            sa.Column("quantity_on_hand", sa.Numeric(12, 3), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_erp_inventory_items_project_id", "erp_inventory_items", ["project_id"])
        op.create_index("ix_erp_inventory_items_sku", "erp_inventory_items", ["sku"])

    if "erp_inventory_movements" not in existing_tables:
        op.create_table(
            "erp_inventory_movements",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("item_id", sa.String(length=36), nullable=False),
            sa.Column("quantity_delta", sa.Numeric(12, 3), nullable=False),
            sa.Column("reference_record_id", sa.String(length=36), nullable=True),
            sa.Column("reason", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_erp_inventory_movements_item_id", "erp_inventory_movements", ["item_id"])
        op.create_index("ix_erp_inventory_movements_reference_record_id", "erp_inventory_movements", ["reference_record_id"])

    if "erp_payroll_entries" not in existing_tables:
        op.create_table(
            "erp_payroll_entries",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("gestor_user_id", sa.String(length=36), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("reference_record_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_erp_payroll_entries_project_id", "erp_payroll_entries", ["project_id"])
        op.create_index("ix_erp_payroll_entries_gestor_user_id", "erp_payroll_entries", ["gestor_user_id"])
        op.create_index("ix_erp_payroll_entries_reference_record_id", "erp_payroll_entries", ["reference_record_id"])


def downgrade() -> None:
    op.drop_index("ix_erp_payroll_entries_reference_record_id", table_name="erp_payroll_entries")
    op.drop_index("ix_erp_payroll_entries_gestor_user_id", table_name="erp_payroll_entries")
    op.drop_index("ix_erp_payroll_entries_project_id", table_name="erp_payroll_entries")
    op.drop_table("erp_payroll_entries")

    op.drop_index("ix_erp_inventory_movements_reference_record_id", table_name="erp_inventory_movements")
    op.drop_index("ix_erp_inventory_movements_item_id", table_name="erp_inventory_movements")
    op.drop_table("erp_inventory_movements")

    op.drop_index("ix_erp_inventory_items_sku", table_name="erp_inventory_items")
    op.drop_index("ix_erp_inventory_items_project_id", table_name="erp_inventory_items")
    op.drop_table("erp_inventory_items")

    op.drop_index("ix_erp_template_configs_template_id", table_name="erp_template_configs")
    op.drop_table("erp_template_configs")
