"""in-app notification center

Revision ID: 0018_in_app_notifications
Revises: 0017_field_water_sources
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_in_app_notifications"
down_revision = "0017_field_water_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "event_key", name="uq_app_notifications_user_event"),
    )
    op.create_index("ix_app_notifications_user_id", "app_notifications", ["user_id"])
    op.create_index("ix_app_notifications_category", "app_notifications", ["category"])
    op.create_index("ix_app_notifications_is_read", "app_notifications", ["is_read"])
    op.create_index("ix_app_notifications_user_created", "app_notifications", ["user_id", "created_at"])
    op.create_index("ix_app_notifications_user_read", "app_notifications", ["user_id", "is_read"])


def downgrade():
    op.drop_table("app_notifications")
