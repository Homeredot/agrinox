"""smart farming calendar

Revision ID: 0012_smart_farming_calendar
Revises: 0011_satellite_monitoring
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_smart_farming_calendar"
down_revision = "0011_satellite_monitoring"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calendar_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("crop", sa.String(length=80), nullable=True),
        sa.Column("growth_stage", sa.String(length=80), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recurrence", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("recurrence_interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_reminder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("source_title", sa.String(length=300), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_calendar_tasks_owner_id", "calendar_tasks", ["owner_id"])
    op.create_index("ix_calendar_tasks_field_id", "calendar_tasks", ["field_id"])
    op.create_index("ix_calendar_tasks_category", "calendar_tasks", ["category"])
    op.create_index("ix_calendar_tasks_crop", "calendar_tasks", ["crop"])
    op.create_index("ix_calendar_tasks_due_at", "calendar_tasks", ["due_at"])
    op.create_index("ix_calendar_tasks_reminder_at", "calendar_tasks", ["reminder_at"])
    op.create_index("ix_calendar_tasks_status", "calendar_tasks", ["status"])
    op.create_index("ix_calendar_tasks_owner_due", "calendar_tasks", ["owner_id", "due_at"])
    op.create_index("ix_calendar_tasks_field_status", "calendar_tasks", ["field_id", "status"])


def downgrade():
    op.drop_table("calendar_tasks")
