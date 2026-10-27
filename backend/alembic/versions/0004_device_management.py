"""ESP32 devices and sensor readings

Revision ID: 0004_device_management
Revises: 0003_weather_cache
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_device_management"
down_revision = "0003_weather_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("device_uid", sa.String(120), nullable=False),
        sa.Column("board", sa.String(80), nullable=False, server_default="ESP32"),
        sa.Column("port", sa.String(120), nullable=False),
        sa.Column("baud_rate", sa.Integer(), nullable=False, server_default="115200"),
        sa.Column("firmware_version", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="registered"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_devices_owner_id", "devices", ["owner_id"])
    op.create_index("ix_devices_field_id", "devices", ["field_id"])
    op.create_index("ix_devices_device_uid", "devices", ["device_uid"], unique=True)
    op.create_index("ix_devices_owner_field", "devices", ["owner_id", "field_id"])
    op.create_table("sensors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sensor_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sensor_type", sa.String(80), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("pin", sa.String(30), nullable=True),
        sa.Column("latest_value", sa.Float(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sensors_device_id", "sensors", ["device_id"])
    op.create_index("ix_sensors_device_key", "sensors", ["device_id", "sensor_key"], unique=True)
    op.create_table("sensor_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sensor_id", sa.Integer(), sa.ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sensor_readings_sensor_id", "sensor_readings", ["sensor_id"])
    op.create_index("ix_sensor_readings_sensor_time", "sensor_readings", ["sensor_id", "recorded_at"])


def downgrade() -> None:
    op.drop_table("sensor_readings")
    op.drop_table("sensors")
    op.drop_table("devices")
