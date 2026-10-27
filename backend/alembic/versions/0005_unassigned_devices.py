"""Allow registered devices to be unassigned from a field

Revision ID: 0005_unassigned_devices
Revises: 0004_device_management
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_unassigned_devices"
down_revision = "0004_device_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("devices", naming_convention=naming) as batch:
        batch.drop_constraint("fk_devices_field_id_farm_fields", type_="foreignkey")
        batch.alter_column("field_id", existing_type=sa.Integer(), nullable=True)
        batch.create_foreign_key(
            "fk_devices_field_id_farm_fields",
            "farm_fields",
            ["field_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.execute("DELETE FROM devices WHERE field_id IS NULL")
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("devices", naming_convention=naming) as batch:
        batch.drop_constraint("fk_devices_field_id_farm_fields", type_="foreignkey")
        batch.alter_column("field_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_devices_field_id_farm_fields",
            "farm_fields",
            ["field_id"],
            ["id"],
            ondelete="CASCADE",
        )
