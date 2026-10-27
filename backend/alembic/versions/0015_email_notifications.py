"""central email notifications and user preferences

Revision ID: 0015_email_notifications
Revises: 0014_farm_finance
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_email_notifications"
down_revision = "0014_farm_finance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("calendar_reminders", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("irrigation_events", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("device_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("soil_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("plant_results", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("planning_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("finance_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("security_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True)
    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=180), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_deliveries_user_id", "email_deliveries", ["user_id"])
    op.create_index("ix_email_deliveries_category", "email_deliveries", ["category"])
    op.create_index("ix_email_deliveries_event_key", "email_deliveries", ["event_key"], unique=True)
    op.create_index("ix_email_deliveries_status", "email_deliveries", ["status"])
    op.create_index("ix_email_deliveries_user_created", "email_deliveries", ["user_id", "created_at"])
    op.create_index("ix_email_deliveries_category_created", "email_deliveries", ["category", "created_at"])


def downgrade():
    op.drop_table("email_deliveries")
    op.drop_table("notification_preferences")
