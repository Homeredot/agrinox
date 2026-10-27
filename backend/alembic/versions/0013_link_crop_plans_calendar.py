"""link crop plans to calendar tasks

Revision ID: 0013_link_crop_plans_calendar
Revises: 0012_smart_farming_calendar
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_link_crop_plans_calendar"
down_revision = "0012_smart_farming_calendar"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("calendar_tasks") as batch:
        batch.add_column(sa.Column("crop_plan_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_calendar_tasks_crop_plan", "crop_plans", ["crop_plan_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_calendar_tasks_crop_plan_id", ["crop_plan_id"])


def downgrade():
    with op.batch_alter_table("calendar_tasks") as batch:
        batch.drop_index("ix_calendar_tasks_crop_plan_id")
        batch.drop_constraint("fk_calendar_tasks_crop_plan", type_="foreignkey")
        batch.drop_column("crop_plan_id")
