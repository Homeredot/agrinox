"""satellite monitoring saved coordinate areas

Revision ID: 0011_satellite_monitoring
Revises: 0010_plant_lens
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_satellite_monitoring"
down_revision = "0010_plant_lens"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "satellite_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("radius_m", sa.Float(), nullable=False),
        sa.Column("geometry_geojson", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_satellite_areas_owner_id", "satellite_areas", ["owner_id"])
    op.create_index("ix_satellite_areas_owner_created", "satellite_areas", ["owner_id", "created_at"])


def downgrade():
    op.drop_table("satellite_areas")
