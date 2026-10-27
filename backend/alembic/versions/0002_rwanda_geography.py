"""normalized Rwanda administrative geography

Revision ID: 0002_rwanda_geography
Revises: 0001_module0
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_rwanda_geography"
down_revision = "0001_module0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("provinces",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True))
    op.create_table("districts",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("province_code", sa.Integer(), sa.ForeignKey("provinces.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.UniqueConstraint("province_code", "name", name="uq_district_province_name"))
    op.create_index("ix_districts_province", "districts", ["province_code"])
    op.create_table("sectors",
        sa.Column("code", sa.String(12), primary_key=True),
        sa.Column("district_code", sa.Integer(), sa.ForeignKey("districts.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.UniqueConstraint("district_code", "name", name="uq_sector_district_name"))
    op.create_index("ix_sectors_district", "sectors", ["district_code"])
    op.create_table("cells",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("sector_code", sa.String(12), sa.ForeignKey("sectors.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.UniqueConstraint("sector_code", "name", name="uq_cell_sector_name"))
    op.create_index("ix_cells_sector", "cells", ["sector_code"])
    op.create_table("villages",
        sa.Column("code", sa.Integer(), primary_key=True),
        sa.Column("cell_code", sa.Integer(), sa.ForeignKey("cells.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("cell_code", "name", name="uq_village_cell_name"))
    op.create_index("ix_villages_cell", "villages", ["cell_code"])
    with op.batch_alter_table("farms") as batch:
        batch.add_column(sa.Column("province_code", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("district_code", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sector_code", sa.String(12), nullable=True))
        batch.add_column(sa.Column("cell_code", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("village_code", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_farm_province", "provinces", ["province_code"], ["code"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_farm_district", "districts", ["district_code"], ["code"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_farm_sector", "sectors", ["sector_code"], ["code"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_farm_cell", "cells", ["cell_code"], ["code"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_farm_village", "villages", ["village_code"], ["code"], ondelete="RESTRICT")
        batch.create_index("ix_farms_village_code", ["village_code"])


def downgrade() -> None:
    with op.batch_alter_table("farms") as batch:
        batch.drop_index("ix_farms_village_code")
        for name in ["fk_farm_village", "fk_farm_cell", "fk_farm_sector", "fk_farm_district", "fk_farm_province"]:
            batch.drop_constraint(name, type_="foreignkey")
        for column in ["village_code", "cell_code", "sector_code", "district_code", "province_code"]:
            batch.drop_column(column)
    op.drop_table("villages")
    op.drop_table("cells")
    op.drop_table("sectors")
    op.drop_table("districts")
    op.drop_table("provinces")
