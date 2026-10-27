"""field irrigation water sources

Revision ID: 0017_field_water_sources
Revises: 0016_two_factor_authentication
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_field_water_sources"
down_revision = "0016_two_factor_authentication"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "water_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("farm_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sensor_id", sa.Integer(), sa.ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("capacity_liters", sa.Float(), nullable=True),
        sa.Column("tank_height_cm", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("capacity_liters IS NULL OR capacity_liters > 0", name="ck_water_source_capacity_positive"),
        sa.CheckConstraint("tank_height_cm IS NULL OR tank_height_cm > 0", name="ck_water_source_height_positive"),
    )
    op.create_index("ix_water_sources_field_id", "water_sources", ["field_id"])
    op.create_index("ix_water_sources_sensor_id", "water_sources", ["sensor_id"], unique=True)
    op.create_index("ix_water_sources_source_type", "water_sources", ["source_type"])
    op.create_index("ix_water_sources_field_primary", "water_sources", ["field_id", "is_primary"])


def downgrade():
    op.drop_table("water_sources")
