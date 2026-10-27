"""crop planning and transparent yield baseline

Revision ID: 0008_crop_planning
Revises: 0007_knowledge_base
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_crop_planning"
down_revision = "0007_knowledge_base"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crop_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crop", sa.String(length=80), nullable=False),
        sa.Column("season", sa.String(length=1), nullable=False),
        sa.Column("planned_planting_date", sa.Date(), nullable=False),
        sa.Column("irrigation", sa.String(length=30), nullable=False),
        sa.Column("previous_crop", sa.String(length=80), nullable=True),
        sa.Column("previous_harvest_tonnes", sa.Float(), nullable=True),
        sa.Column("soil_notes", sa.String(length=500), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crop_plans_owner_id", "crop_plans", ["owner_id"])
    op.create_index("ix_crop_plans_field_id", "crop_plans", ["field_id"])
    op.create_index("ix_crop_plans_owner_created", "crop_plans", ["owner_id", "created_at"])


def downgrade():
    op.drop_index("ix_crop_plans_owner_created", table_name="crop_plans")
    op.drop_index("ix_crop_plans_field_id", table_name="crop_plans")
    op.drop_index("ix_crop_plans_owner_id", table_name="crop_plans")
    op.drop_table("crop_plans")
