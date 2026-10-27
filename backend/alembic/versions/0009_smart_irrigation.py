"""smart irrigation safety and device telemetry

Revision ID: 0009_smart_irrigation
Revises: 0008_crop_planning
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_smart_irrigation"
down_revision = "0008_crop_planning"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("api_key_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("remote_control_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("sensor_readings") as batch:
        batch.add_column(sa.Column("valid", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "irrigation_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="advisory"),
        sa.Column("safety_validated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remote_control_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("emergency_stop", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_pump_runtime_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("min_tank_percent", sa.Float(), nullable=False, server_default="15"),
        sa.Column("max_reading_age_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("moisture_trigger_percent", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("field_id"),
    )
    op.create_index("ix_irrigation_configs_field_id", "irrigation_configs", ["field_id"], unique=True)
    op.create_table(
        "irrigation_commands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command", sa.String(length=30), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason_json", sa.Text(), nullable=False),
        sa.Column("execution_message", sa.String(length=500), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_irrigation_commands_field_id", "irrigation_commands", ["field_id"])
    op.create_index("ix_irrigation_commands_device_id", "irrigation_commands", ["device_id"])
    op.create_index("ix_irrigation_commands_requested_by_user_id", "irrigation_commands", ["requested_by_user_id"])
    op.create_index("ix_irrigation_commands_field_time", "irrigation_commands", ["field_id", "issued_at"])


def downgrade():
    op.drop_table("irrigation_commands")
    op.drop_table("irrigation_configs")
    with op.batch_alter_table("sensor_readings") as batch:
        batch.drop_column("simulated")
        batch.drop_column("valid")
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("remote_control_enabled")
        batch.drop_column("api_key_hash")
