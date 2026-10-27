"""farm profit and expense calculator

Revision ID: 0014_farm_finance
Revises: 0013_link_crop_plans_calendar
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_farm_finance"
down_revision = "0013_link_crop_plans_calendar"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financial_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crop_plan_id", sa.Integer(), sa.ForeignKey("crop_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("crop", sa.String(length=80), nullable=True),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("expected_harvest_kg", sa.Float(), nullable=False),
        sa.Column("selling_price_per_kg_rwf", sa.Float(), nullable=False),
        sa.Column("expenses_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_financial_plans_owner_id", "financial_plans", ["owner_id"])
    op.create_index("ix_financial_plans_field_id", "financial_plans", ["field_id"])
    op.create_index("ix_financial_plans_crop_plan_id", "financial_plans", ["crop_plan_id"])
    op.create_index("ix_financial_plans_owner_created", "financial_plans", ["owner_id", "created_at"])
    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("financial_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("amount_rwf", sa.Float(), nullable=False),
        sa.Column("quantity_kg", sa.Float(), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_financial_transactions_owner_id", "financial_transactions", ["owner_id"])
    op.create_index("ix_financial_transactions_plan_id", "financial_transactions", ["plan_id"])
    op.create_index("ix_financial_transactions_plan_date", "financial_transactions", ["plan_id", "occurred_on"])


def downgrade():
    op.drop_table("financial_transactions")
    op.drop_table("financial_plans")
