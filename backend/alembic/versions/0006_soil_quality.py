"""Soil quality readings and crop context

Revision ID: 0006_soil_quality
Revises: 0005_unassigned_devices
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_soil_quality"
down_revision = "0005_unassigned_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "soil_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crop_type", sa.String(80), nullable=True),
        sa.Column("growth_stage", sa.String(80), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_soil_contexts_field_id", "soil_contexts", ["field_id"], unique=True)
    op.create_table(
        "soil_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measurement_type", sa.String(30), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("calibration_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("reliability", sa.String(30), nullable=False, server_default="needs_review"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_soil_readings_owner_id", "soil_readings", ["owner_id"])
    op.create_index("ix_soil_readings_field_id", "soil_readings", ["field_id"])
    op.create_index("ix_soil_readings_field_type_time", "soil_readings", ["field_id", "measurement_type", "measured_at"])


def downgrade() -> None:
    op.drop_table("soil_readings")
    op.drop_table("soil_contexts")
